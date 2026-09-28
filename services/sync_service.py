import logging

from models.market_news import MarketNews
from repositories.news_repository import NewsRepository
from services.aggregator_service import get_all_news_with_stats, normalise_url

logger = logging.getLogger(__name__)


class SyncService:
    @staticmethod
    def sync_news(db):
        all_news, provider_summary = get_all_news_with_stats()

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
                with db.begin_nested():
                    NewsRepository.save_news(db, news)
                    db.flush()
                existing_urls.add(news["url"])
                saved += 1
            except Exception:
                failed += 1
                logger.exception("Could not save news article with URL %s", news["url"])

        db.commit()

        total_fetched = sum(p.get("count", 0) for p in provider_summary.values())

        logger.info(
            "[NEWS][AGGREGATOR] Total fetched: %d | New articles: %d | Duplicates: %d",
            total_fetched, saved, duplicate,
        )

        return {
            # Existing fields — unchanged so frontend/backend code keeps working
            "totalFetched": len(all_news),
            "saved": saved,
            "duplicate": duplicate,
            "skipped": skipped,
            "failed": failed,
            # New provider-level breakdown
            "providers": provider_summary,
        }
