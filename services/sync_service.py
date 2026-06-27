from services.aggregator_service import get_all_news
from repositories.news_repository import NewsRepository
from models.market_news import MarketNews


class SyncService:

    @staticmethod
    def sync_news(db):

        # Fetch all news
        all_news = get_all_news()

        total = len(all_news)
        saved = 0
        duplicate = 0

        print("=" * 100)
        print(f"Total News Fetched : {total}")
        print("=" * 100)

        # Fetch all existing URLs only once (Fast Duplicate Check)
        existing_urls = {
            row.url
            for row in db.query(MarketNews.url).all()
        }

        for news in all_news:

            # Skip if URL not found
            if not news.get("url"):
                continue

            try:

                # Duplicate check
                if news["url"] in existing_urls:
                    duplicate += 1
                    continue

                # Save in SQLAlchemy session
                NewsRepository.save_news(
                    db,
                    news
                )

                # Add URL to memory to avoid duplicates in same sync
                existing_urls.add(news["url"])

                saved += 1

            except Exception as e:

                print("=" * 100)
                print("ERROR SAVING NEWS")
                print("Title :", news.get("title"))
                print("URL   :", news.get("url"))
                print("Error :", e)
                print("=" * 100)

                db.rollback()

        # Single Commit (Fast)
        db.commit()

        print("=" * 100)
        print(f"Saved      : {saved}")
        print(f"Duplicate  : {duplicate}")
        print("=" * 100)

        return {
            "totalFetched": total,
            "saved": saved,
            "duplicate": duplicate
        }