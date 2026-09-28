"""
Tests for the multi-provider news architecture.

Run with:  pytest tests/test_news_providers.py -v
"""

import time
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_article(title="Test Article", url="https://example.com/1", provider="test"):
    return {
        "title": title,
        "description": "desc",
        "source": provider,
        "url": url,
        "published": "2024-01-01T00:00:00",
        "sentiment": None,
        "provider": provider,
        "provider_article_id": None,
        "symbols": [],
        "entities": [],
        "category": None,
        "sentiment_score": None,
        "relevance_score": None,
    }


def _reset_providers():
    """Clear provider registry and health between tests."""
    import services.news_provider_manager as mgr
    mgr._providers.clear()
    mgr._health.clear()


# ---------------------------------------------------------------------------
# Test 1 — All providers healthy
# ---------------------------------------------------------------------------
def test_all_providers_healthy():
    _reset_providers()
    import services.news_provider_manager as mgr

    mgr.register_provider("p1", "primary", lambda: [_make_article(url="https://a.com/1", provider="p1")])
    mgr.register_provider("p2", "primary", lambda: [_make_article(url="https://b.com/1", provider="p2")])

    articles, summary = mgr.fetch_all_providers()

    assert len(articles) == 2
    assert summary["p1"]["status"] == mgr.STATUS_HEALTHY
    assert summary["p2"]["status"] == mgr.STATUS_HEALTHY


# ---------------------------------------------------------------------------
# Test 2 — Benzinga timeout, others continue
# ---------------------------------------------------------------------------
def test_benzinga_timeout_others_continue():
    _reset_providers()
    import services.news_provider_manager as mgr

    def slow_provider():
        time.sleep(60)  # will be killed by timeout
        return []

    mgr.register_provider("benzinga", "primary", slow_provider)
    mgr.register_provider("marketaux", "primary", lambda: [_make_article(url="https://m.com/1", provider="marketaux")])

    # Patch timeout to 1s so test is fast
    with patch.object(mgr, "_TIMEOUT", 1):
        articles, summary = mgr.fetch_all_providers()

    # marketaux must succeed
    assert summary["marketaux"]["status"] == mgr.STATUS_HEALTHY
    assert summary["marketaux"]["count"] == 1
    # benzinga must be timeout/degraded, not crash
    assert summary["benzinga"]["status"] in (mgr.STATUS_TIMEOUT, mgr.STATUS_DEGRADED)
    assert summary["benzinga"]["count"] == 0


# ---------------------------------------------------------------------------
# Test 3 — MarketAux failure, others continue
# ---------------------------------------------------------------------------
def test_marketaux_failure_others_continue():
    _reset_providers()
    import services.news_provider_manager as mgr

    mgr.register_provider("marketaux", "primary", lambda: (_ for _ in ()).throw(RuntimeError("connection refused")))
    mgr.register_provider("newsapi", "backup", lambda: [_make_article(url="https://n.com/1", provider="newsapi")])

    articles, summary = mgr.fetch_all_providers()

    assert summary["newsapi"]["status"] == mgr.STATUS_HEALTHY
    assert summary["marketaux"]["status"] != mgr.STATUS_HEALTHY


# ---------------------------------------------------------------------------
# Test 4 — Finnhub 429, no infinite retry
# ---------------------------------------------------------------------------
def test_finnhub_rate_limited_no_infinite_retry():
    _reset_providers()
    import services.news_provider_manager as mgr

    call_count = {"n": 0}

    def rate_limited():
        call_count["n"] += 1
        raise RuntimeError("HTTP 429 — rate limit")

    mgr.register_provider("finnhub", "secondary", rate_limited)

    articles, summary = mgr.fetch_all_providers()

    assert summary["finnhub"]["status"] == mgr.STATUS_RATE_LIMITED
    # Auth/rate-limit errors must NOT be retried (max 1 call)
    assert call_count["n"] == 1


# ---------------------------------------------------------------------------
# Test 5 — Invalid API key, no repeated retries
# ---------------------------------------------------------------------------
def test_invalid_api_key_no_retry():
    _reset_providers()
    import services.news_provider_manager as mgr

    call_count = {"n": 0}

    def auth_error():
        call_count["n"] += 1
        raise RuntimeError("HTTP 401 — authentication error")

    mgr.register_provider("benzinga", "primary", auth_error)

    articles, summary = mgr.fetch_all_providers()

    assert summary["benzinga"]["status"] == mgr.STATUS_AUTH_ERROR
    assert call_count["n"] == 1  # no retry on auth errors


# ---------------------------------------------------------------------------
# Test 6 — Same article from multiple providers → deduplicated
# ---------------------------------------------------------------------------
def test_deduplication_preserves_first_seen():
    from services.aggregator_service import _fetch_and_deduplicate
    import services.news_provider_manager as mgr
    _reset_providers()

    shared_url = "https://shared.com/breaking-news"
    mgr.register_provider("benzinga", "primary", lambda: [_make_article(url=shared_url, provider="benzinga")])
    mgr.register_provider("marketaux", "primary", lambda: [_make_article(url=shared_url, provider="marketaux")])
    mgr.register_provider("finnhub", "secondary", lambda: [_make_article(url=shared_url, provider="finnhub")])

    articles, summary = _fetch_and_deduplicate()

    # Only one article should survive deduplication
    matching = [a for a in articles if a.get("url") and shared_url in a["url"]]
    assert len(matching) == 1


# ---------------------------------------------------------------------------
# Test 7 — All new providers fail, NewsAPI + Google RSS still work
# ---------------------------------------------------------------------------
def test_backup_providers_work_when_primaries_fail():
    _reset_providers()
    import services.news_provider_manager as mgr

    def fail():
        raise RuntimeError("provider down")

    mgr.register_provider("benzinga", "primary", fail)
    mgr.register_provider("marketaux", "primary", fail)
    mgr.register_provider("alpha_vantage", "secondary", fail)
    mgr.register_provider("finnhub", "secondary", fail)
    mgr.register_provider("newsapi", "backup", lambda: [_make_article(url="https://newsapi.com/1", provider="newsapi")])
    mgr.register_provider("google_news", "backup", lambda: [_make_article(url="https://google.com/1", provider="google_news")])

    articles, summary = mgr.fetch_all_providers()

    assert summary["newsapi"]["status"] == mgr.STATUS_HEALTHY
    assert summary["google_news"]["status"] == mgr.STATUS_HEALTHY
    assert len(articles) == 2


# ---------------------------------------------------------------------------
# Test 8 — All providers unavailable → graceful finish, no crash
# ---------------------------------------------------------------------------
def test_all_providers_unavailable_graceful():
    _reset_providers()
    import services.news_provider_manager as mgr

    def fail():
        raise RuntimeError("all down")

    for name in ["benzinga", "marketaux", "alpha_vantage", "finnhub", "newsapi", "google_news"]:
        mgr.register_provider(name, "primary", fail)

    # Must not raise
    articles, summary = mgr.fetch_all_providers()

    assert articles == []
    assert all(s["count"] == 0 for s in summary.values())


# ---------------------------------------------------------------------------
# Test 9 — Circuit breaker: after threshold failures, provider is skipped
# ---------------------------------------------------------------------------
def test_circuit_breaker_skips_after_threshold():
    _reset_providers()
    import services.news_provider_manager as mgr

    call_count = {"n": 0}

    def flaky():
        call_count["n"] += 1
        raise RuntimeError("server error 500")

    mgr.register_provider("flaky_provider", "primary", flaky)

    # Trigger enough failures to open the circuit
    threshold = mgr._FAILURE_THRESHOLD
    for _ in range(threshold):
        mgr._call_provider("flaky_provider", "primary", flaky)

    health = mgr._health["flaky_provider"]
    assert health.is_circuit_open()

    # Next call should be skipped (circuit open)
    before = call_count["n"]
    result = mgr._call_provider("flaky_provider", "primary", flaky)
    assert call_count["n"] == before  # fetch_fn was NOT called
    assert result.status == mgr.STATUS_DEGRADED


# ---------------------------------------------------------------------------
# Test 10 — Health API returns correct statuses
# ---------------------------------------------------------------------------
def test_health_api_returns_correct_statuses():
    _reset_providers()
    import services.news_provider_manager as mgr

    mgr.register_provider("healthy_p", "primary", lambda: [_make_article(url="https://h.com/1")])
    mgr.register_provider("failing_p", "secondary", lambda: (_ for _ in ()).throw(RuntimeError("HTTP 429")))

    mgr.fetch_all_providers()

    health_list = mgr.get_all_provider_health()
    by_name = {h["name"]: h for h in health_list}

    assert by_name["healthy_p"]["status"] == mgr.STATUS_HEALTHY
    assert by_name["failing_p"]["status"] == mgr.STATUS_RATE_LIMITED

    # Must never expose API keys
    for h in health_list:
        for v in h.values():
            if isinstance(v, str):
                assert "key" not in v.lower()
                assert "token" not in v.lower()
                assert "secret" not in v.lower()
