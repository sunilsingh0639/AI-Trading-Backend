from sqlalchemy.orm import Session
from models.market_news import MarketNews


class NewsRepository:

    @staticmethod
    def is_duplicate(db: Session, url: str):

        return (
            db.query(MarketNews)
            .filter(MarketNews.url == url)
            .first()
        )

    @staticmethod
    def save_news(db: Session, news):
        import json as _json

        # Serialise provider symbols list → JSON string for storage
        symbols_raw = news.get("symbols")
        symbols_str: str | None = None
        if symbols_raw and isinstance(symbols_raw, list):
            clean = [str(s) for s in symbols_raw if s]
            if clean:
                symbols_str = _json.dumps(clean)

        # Serialise provider entity names list → JSON string for storage
        entities_raw = news.get("entities")
        entities_str: str | None = None
        if entities_raw and isinstance(entities_raw, list):
            # Each entity may be a dict {name, symbol, ...} or a plain string.
            # We store only the name strings so resolve_symbol() can match them.
            names = []
            for e in entities_raw:
                if isinstance(e, dict):
                    name = (e.get("name") or "").strip()
                    if name:
                        names.append(name)
                elif isinstance(e, str) and e.strip():
                    names.append(e.strip())
            if names:
                entities_str = _json.dumps(names)

        db_news = MarketNews(
            title=news.get("title"),
            description=news.get("description"),
            source=news.get("source"),
            url=news.get("url"),
            published=news.get("published"),
            sentiment=news.get("sentiment"),
            symbols=symbols_str,
            entities=entities_str,
            provider=news.get("provider"),
        )

        db.add(db_news)

        return db_news

    @staticmethod
    def get_pending_news(db: Session, limit: int = 10):

        return (
            db.query(MarketNews)
            .filter(MarketNews.ai_status == False)
            .order_by(MarketNews.id.desc())
            .limit(limit)
            .all()
        )

    @staticmethod
    def update_ai_status(db: Session, news):

        news.ai_status = True
        db.flush()

        return news
