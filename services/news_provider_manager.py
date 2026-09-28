"""
Non-blocking news provider manager.

Calls all providers in parallel with per-provider timeouts and circuit breakers.
A single provider failure never blocks or stops the pipeline.
"""

import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration (read once at import time; can be overridden via env)
# ---------------------------------------------------------------------------
_TIMEOUT = int(os.getenv("NEWS_PROVIDER_TIMEOUT_SECONDS", "10"))
_FAILURE_THRESHOLD = int(os.getenv("NEWS_PROVIDER_FAILURE_THRESHOLD", "3"))
_COOLDOWN = int(os.getenv("NEWS_PROVIDER_COOLDOWN_SECONDS", "60"))

# ---------------------------------------------------------------------------
# Status constants
# ---------------------------------------------------------------------------
STATUS_HEALTHY = "healthy"
STATUS_DEGRADED = "degraded"
STATUS_TIMEOUT = "timeout"
STATUS_RATE_LIMITED = "rate_limited"
STATUS_AUTH_ERROR = "auth_error"
STATUS_SERVER_ERROR = "server_error"
STATUS_NETWORK_ERROR = "network_error"
STATUS_EMPTY_RESPONSE = "empty_response"
STATUS_INVALID_RESPONSE = "invalid_response"
STATUS_DISABLED = "disabled"


# ---------------------------------------------------------------------------
# Per-provider health record (in-memory, reset on restart)
# ---------------------------------------------------------------------------
@dataclass
class ProviderHealth:
    name: str
    priority: str  # primary | secondary | backup
    status: str = STATUS_HEALTHY
    last_success_at: Optional[str] = None
    last_failure_at: Optional[str] = None
    last_attempt_at: Optional[str] = None
    response_time_ms: int = 0
    articles_received: int = 0
    error_count: int = 0
    last_error: Optional[str] = None
    consecutive_failures: int = 0
    _circuit_open_since: Optional[float] = field(default=None, repr=False)

    def is_circuit_open(self) -> bool:
        if self._circuit_open_since is None:
            return False
        if time.monotonic() - self._circuit_open_since >= _COOLDOWN:
            # Cooldown elapsed — reset circuit
            self._circuit_open_since = None
            self.consecutive_failures = 0
            self.status = STATUS_DEGRADED
            return False
        return True

    def record_success(self, articles: int, elapsed_ms: int):
        now = datetime.now(timezone.utc).isoformat()
        self.status = STATUS_HEALTHY
        self.last_success_at = now
        self.last_attempt_at = now
        self.response_time_ms = elapsed_ms
        self.articles_received = articles
        self.consecutive_failures = 0
        self._circuit_open_since = None
        self.last_error = None

    def record_failure(self, status: str, error: str, elapsed_ms: int):
        now = datetime.now(timezone.utc).isoformat()
        self.status = status
        self.last_failure_at = now
        self.last_attempt_at = now
        self.response_time_ms = elapsed_ms
        self.articles_received = 0
        self.error_count += 1
        self.last_error = error
        self.consecutive_failures += 1
        if self.consecutive_failures >= _FAILURE_THRESHOLD:
            self._circuit_open_since = time.monotonic()
            logger.warning(
                "[NEWS][%s] Circuit open after %d consecutive failures. Cooldown %ds.",
                self.name.upper(), self.consecutive_failures, _COOLDOWN,
            )


# ---------------------------------------------------------------------------
# Global health registry
# ---------------------------------------------------------------------------
_health: dict[str, ProviderHealth] = {}


def _get_health(name: str, priority: str) -> ProviderHealth:
    if name not in _health:
        _health[name] = ProviderHealth(name=name, priority=priority)
    return _health[name]


def get_all_provider_health() -> list[dict]:
    return [
        {
            "name": h.name,
            "priority": h.priority,
            "status": h.status,
            "last_success_at": h.last_success_at,
            "last_failure_at": h.last_failure_at,
            "last_attempt_at": h.last_attempt_at,
            "response_time_ms": h.response_time_ms,
            "articles_received": h.articles_received,
            "error_count": h.error_count,
            "last_error": h.last_error,
            "consecutive_failures": h.consecutive_failures,
        }
        for h in _health.values()
    ]


# ---------------------------------------------------------------------------
# ProviderResult — what each provider must return
# ---------------------------------------------------------------------------
@dataclass
class ProviderResult:
    provider: str
    status: str
    articles: list[dict]
    count: int
    response_time_ms: int
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# _call_provider — wraps a single provider fetch with timeout + error mapping
# ---------------------------------------------------------------------------
def _classify_error(exc: Exception) -> str:
    msg = str(exc).lower()
    if "429" in msg or "rate limit" in msg or "too many requests" in msg:
        return STATUS_RATE_LIMITED
    if "401" in msg or "403" in msg or "authentication" in msg or "api key" in msg or "unauthorized" in msg:
        return STATUS_AUTH_ERROR
    if "5" in msg and ("500" in msg or "502" in msg or "503" in msg or "504" in msg):
        return STATUS_SERVER_ERROR
    if "timeout" in msg or "timed out" in msg or "read timeout" in msg:
        return STATUS_TIMEOUT
    if "connection" in msg or "network" in msg or "name or service" in msg:
        return STATUS_NETWORK_ERROR
    if "json" in msg or "invalid" in msg or "unexpected" in msg:
        return STATUS_INVALID_RESPONSE
    return STATUS_SERVER_ERROR


def _call_provider(
    name: str,
    priority: str,
    fetch_fn: Callable[[], list[dict]],
) -> ProviderResult:
    health = _get_health(name, priority)

    if health.is_circuit_open():
        logger.info("[NEWS][%s] Circuit open — skipping (cooldown active).", name.upper())
        return ProviderResult(
            provider=name, status=STATUS_DEGRADED, articles=[], count=0,
            response_time_ms=0, error="Circuit open — cooldown active",
        )

    logger.info("[NEWS][%s] Fetch started", name.upper())
    t0 = time.monotonic()

    # Retry logic: max 1 retry for timeout/5xx, no retry for 4xx auth
    last_exc = None
    for attempt in range(2):
        try:
            articles = fetch_fn()
            elapsed = int((time.monotonic() - t0) * 1000)
            if not isinstance(articles, list):
                raise ValueError(f"Expected list, got {type(articles).__name__}")
            health.record_success(len(articles), elapsed)
            logger.info(
                "[NEWS][%s] SUCCESS | Articles: %d | Response: %dms",
                name.upper(), len(articles), elapsed,
            )
            return ProviderResult(
                provider=name, status=STATUS_HEALTHY,
                articles=articles, count=len(articles),
                response_time_ms=elapsed,
            )
        except Exception as exc:
            last_exc = exc
            status = _classify_error(exc)
            # Do not retry auth errors
            if status == STATUS_AUTH_ERROR:
                break
            # Only retry once for timeout/server errors
            if attempt == 0 and status in (STATUS_TIMEOUT, STATUS_SERVER_ERROR):
                logger.debug("[NEWS][%s] Attempt 1 failed (%s), retrying once.", name.upper(), status)
                time.sleep(1)
                continue
            break

    elapsed = int((time.monotonic() - t0) * 1000)
    status = _classify_error(last_exc)
    error_msg = str(last_exc)
    health.record_failure(status, error_msg, elapsed)
    logger.warning("[NEWS][%s] %s | %s | %dms", name.upper(), status.upper(), error_msg, elapsed)
    return ProviderResult(
        provider=name, status=status, articles=[], count=0,
        response_time_ms=elapsed, error=error_msg,
    )


# ---------------------------------------------------------------------------
# Provider registry entry
# ---------------------------------------------------------------------------
@dataclass
class _ProviderEntry:
    name: str
    priority: str
    fetch_fn: Callable[[], list[dict]]


_providers: list[_ProviderEntry] = []


def register_provider(name: str, priority: str, fetch_fn: Callable[[], list[dict]]):
    """Register a provider. Called once at startup by each provider module."""
    _providers.append(_ProviderEntry(name=name, priority=priority, fetch_fn=fetch_fn))
    _get_health(name, priority)  # ensure health record exists


# ---------------------------------------------------------------------------
# fetch_all_providers — parallel execution with hard timeout per provider
# ---------------------------------------------------------------------------
def fetch_all_providers() -> tuple[list[dict], dict[str, dict]]:
    """
    Call all registered providers in parallel.
    Returns (normalized_articles, provider_summary).
    Never raises — failed providers are recorded and skipped.
    """
    if not _providers:
        logger.warning("[NEWS][MANAGER] No providers registered.")
        return [], {}

    results: list[ProviderResult] = []

    with ThreadPoolExecutor(max_workers=len(_providers), thread_name_prefix="news_provider") as pool:
        future_to_entry = {
            pool.submit(_call_provider, entry.name, entry.priority, entry.fetch_fn): entry
            for entry in _providers
        }
        for future in as_completed(future_to_entry, timeout=_TIMEOUT + 5):
            entry = future_to_entry[future]
            try:
                result = future.result(timeout=_TIMEOUT + 2)
            except FuturesTimeoutError:
                elapsed = (_TIMEOUT + 2) * 1000
                health = _get_health(entry.name, entry.priority)
                health.record_failure(STATUS_TIMEOUT, "Future timeout", elapsed)
                logger.warning("[NEWS][%s] TIMEOUT (future level)", entry.name.upper())
                result = ProviderResult(
                    provider=entry.name, status=STATUS_TIMEOUT,
                    articles=[], count=0, response_time_ms=elapsed,
                    error="Request timeout",
                )
            except Exception as exc:
                elapsed = 0
                health = _get_health(entry.name, entry.priority)
                health.record_failure(STATUS_SERVER_ERROR, str(exc), elapsed)
                result = ProviderResult(
                    provider=entry.name, status=STATUS_SERVER_ERROR,
                    articles=[], count=0, response_time_ms=0, error=str(exc),
                )
            results.append(result)

    all_articles: list[dict] = []
    provider_summary: dict[str, dict] = {}

    for r in results:
        all_articles.extend(r.articles)
        provider_summary[r.provider] = {"status": r.status, "count": r.count}

    total_fetched = sum(r.count for r in results)
    logger.info(
        "[NEWS][MANAGER] Total fetched: %d from %d providers (%d failed)",
        total_fetched,
        len(results),
        sum(1 for r in results if r.status != STATUS_HEALTHY),
    )
    return all_articles, provider_summary
