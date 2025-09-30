import asyncio
import random
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

from database.database_service import db_service
from core.context_logger import ContextLogger

publisher_context_logger = ContextLogger("publisher")

class ContentPublisher:
    """
    A basic agent to simulate publishing content.
    In a real scenario, this would interact with a CMS, social media API, or database.
    """
    def __init__(self):
        self.context_logger = publisher_context_logger
        self.context_logger.logger.info("ContentPublisher initialized.")

    @publisher_context_logger.log_execution
    async def publish_content(self, content_data: Dict[str, Any], article_id: Optional[str] = None, publish_immediately: bool = False) -> bool:
        """
        Simulates publishing a piece of content.

        Args:
            content_data (Dict[str, Any]): The content to publish, expected to contain:
                                           'title', 'content', 'author', 'url', 'source_type' (e.g., 'youtube', 'news')
            article_id (Optional[str]): The ID of the article in Supabase, if it exists.
            publish_immediately (bool): If True, publishes without scheduling delay.

        Returns:
            bool: True if publication was simulated successfully, False otherwise.
        """
        title = content_data.get('title', 'Untitled')
        source_type = content_data.get('source_type', 'unknown')

        if not content_data.get('content'):
            self.context_logger.logger.warning("Cannot publish: Missing content.", title=title, source_type=source_type)
            return False

        success = False
        if publish_immediately:
            publish_time = datetime.now()
            self.context_logger.logger.info("Publishing immediately", title=title, source_type=source_type, publish_time=publish_time.isoformat())
            # Simulate API call or database write
            await asyncio.sleep(random.uniform(0.5, 2.0)) # Simulate network delay
            self.context_logger.logger.info("Successfully simulated immediate publication", title=title, source_type=source_type)
            success = True
        else:
            # Intelligent scheduling: publish sometime in the next 1-6 hours
            delay_hours = random.uniform(1, 6)
            publish_time = datetime.now() + timedelta(hours=delay_hours)
            self.context_logger.logger.info("Scheduling for publication", title=title, source_type=source_type, publish_time=publish_time.isoformat(), delay_hours=f"{delay_hours:.2f}")
            # In a real system, this would enqueue a task for later execution or store in a scheduled queue.
            # For this simulation, we'll just log the schedule.
            success = True

        if success and article_id:
            # Actualizar artículo a "published"
            await db_service.update_article_status(article_id, "published")
            self.context_logger.logger.info("Article status updated to published", article_id=article_id)

        return success

# Example usage (for testing purposes)
async def main():
    publisher = ContentPublisher()

    # Example YouTube content
    youtube_content = {
        "title": "AI Trends 2025 Explained",
        "content": "This is the summary of the trending AI video...",
        "author": "Tech Insights",
        "url": "https://www.youtube.com/watch?v=example",
        "embed_url": "https://www.youtube.com/embed/example",
        "source_type": "youtube"
    }
    await publisher.publish_content(youtube_content, publish_immediately=True)
    await publisher.publish_content(youtube_content)

    print("-" * 30)

    # Example News content
    news_content = {
        "title": "Breakthrough in Quantum Computing",
        "content": "Scientists have announced a major breakthrough...",
        "author": "Dr. Alice Smith",
        "date": "2025-09-29",
        "url": "https://example.com/news/quantum",
        "source_type": "news"
    }
    await publisher.publish_content(news_content, publish_immediately=True)
    await publisher.publish_content(news_content)

if __name__ == "__main__":
    asyncio.run(main())
