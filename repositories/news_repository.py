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

        db_news = MarketNews(
            title=news.get("title"),
            description=news.get("description"),
            source=news.get("source"),
            url=news.get("url"),
            published=news.get("published"),
            sentiment=news.get("sentiment")
        )

        db.add(db_news)

        return db_news

    @staticmethod
    def get_pending_news(db: Session):

        return (
            db.query(MarketNews)
            .filter(MarketNews.ai_status == False)
            .order_by(MarketNews.id.desc())
            .limit(10)
            .all()
        )

    @staticmethod
    def update_ai_status(db: Session, news):

        news.ai_status = True

        db.commit()

        db.refresh(news)

        return news