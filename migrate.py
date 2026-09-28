"""Add new pipeline columns to existing tables (idempotent)."""

import logging

from sqlalchemy import inspect, text

from database import engine

logger = logging.getLogger(__name__)

NEWS_ANALYSIS_COLUMNS = {
    "news_type": "VARCHAR(30)",
    "importance_score": "INTEGER",
    "signal_status": "VARCHAR(30)",
    "rejection_reason": "TEXT",
}

PREDICTION_HISTORY_COLUMNS = {
    "risk_reward_ratio": "FLOAT",
    "expected_holding_minutes": "INTEGER",
    "probability": "FLOAT",
    "market_context": "TEXT",
    "supporting_indicators": "TEXT",
}

MARKET_NEWS_COLUMNS = {
    "symbols": "TEXT",
    "provider": "VARCHAR(50)",
}


def _add_missing_columns(table_name: str, columns: dict[str, str]) -> list[str]:
    added: list[str] = []
    inspector = inspect(engine)
    if table_name not in inspector.get_table_names():
        return added

    existing = {column["name"] for column in inspector.get_columns(table_name)}
    with engine.begin() as connection:
        for name, column_type in columns.items():
            if name in existing:
                continue
            connection.execute(
                text(f"ALTER TABLE {table_name} ADD COLUMN {name} {column_type}")
            )
            added.append(name)
            logger.info("Added column %s.%s", table_name, name)
    return added


def run_migrations() -> dict[str, list[str]]:
    return {
        "news_analysis": _add_missing_columns("news_analysis", NEWS_ANALYSIS_COLUMNS),
        "prediction_history": _add_missing_columns(
            "prediction_history", PREDICTION_HISTORY_COLUMNS
        ),
        "market_news": _add_missing_columns("market_news", MARKET_NEWS_COLUMNS),
    }
