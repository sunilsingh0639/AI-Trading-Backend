import logging

from models.market_news import MarketNews
from repositories.news_repository import NewsRepository
from services.aggregator_service import get_all_news, normalise_url

logger = logging.getLogger(__name__)


class SyncService:
    @staticmethod
    def sync_news(db):
        all_news = get_all_news()
        existing_urls = {
            normalise_url(row.url)
            for row in db.query(MarketNews.url).all()
            if row.url
        }

        saved = 0
        duplicate = 0
        skipped = 0
        failed = 0

        for news in all_news:
            news["url"] = normalise_url(news.get("url"))
            if not news["url"] or not (news.get("title") or "").strip():
                skipped += 1
                continue
            if news["url"] in existing_urls:
                duplicate += 1
                continue

            try:
                # A failed row rolls back only its savepoint, not earlier valid news.
                with db.begin_nested():
                    NewsRepository.save_news(db, news)
                    db.flush()
                existing_urls.add(news["url"])
                saved += 1
            except Exception:
                failed += 1
                logger.exception("Could not save news article with URL %s", news["url"])

        db.commit()
        return {
            "totalFetched": len(all_news),
            "saved": saved,
            "duplicate": duplicate,
            "skipped": skipped,
            "failed": failed,
        }
