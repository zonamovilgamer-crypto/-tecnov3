import asyncio
import logging
from celery import Celery, chain, group
from core.celery_config import app
from agents.content_scraper import ContentScraperAgent
from agents.content_writer import HumanizedWriter
from agents.content_publisher import ContentPublisher
from typing import List, Dict, Any, Optional

# Import the global db_service instance
from database.database_service import db_service

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Celery tasks definitions

@app.task(bind=True, queue='scraper_queue', default_retry_delay=60, max_retries=3)
def scrape_youtube_task(self, query: str, max_videos: int = 5) -> List[Dict[str, Any]]:
    """
    Celery task to scrape YouTube video metadata and save it to the database.
    """
    logger.info(f"Celery task: Scraping YouTube for query: '{query}'")

    async def _async_scrape():
        scraper_agent = ContentScraperAgent()
        await scraper_agent.initialize()
        videos = await scraper_agent.find_trending_youtube_videos(query, max_videos)

        # Save scraped videos to the database
        if db_service.is_connected():
            for video_data in videos:
                await db_service.save_video(video_data)
            logger.info(f"Saved {len(videos)} YouTube videos to database for query '{query}'.")
        else:
            logger.warning("Supabase not connected. Skipping saving YouTube video metadata.")

        return videos

    try:
        videos = asyncio.run(_async_scrape())
        logger.info(f"Scraped {len(videos)} YouTube videos for query '{query}'.")
        return videos
    except Exception as e:
        logger.error(f"YouTube scraping task failed for query '{query}': {e}")
        raise self.retry(exc=e)

@app.task(bind=True, queue='scraper_queue', default_retry_delay=60, max_retries=3)
def scrape_news_task(self, search_terms: List[str], news_sources: List[str], max_articles_per_source: int = 2) -> List[Dict[str, Any]]:
    """
    Celery task to scrape news articles and save them to the database.
    """
    logger.info(f"Celery task: Scraping news for terms: {search_terms} from sources: {news_sources}")

    async def _async_scrape_news():
        scraper_agent = ContentScraperAgent()
        await scraper_agent.initialize()
        articles = await scraper_agent.find_popular_news_articles(search_terms, news_sources, max_articles_per_source)

        # Save scraped articles to the database
        if db_service.is_connected():
            for article_data in articles:
                await db_service.save_article(article_data)
            logger.info(f"Saved {len(articles)} news articles to database for terms: {search_terms}.")
        else:
            logger.warning("Supabase not connected. Skipping saving news article data.")

        return articles

    try:
        articles = asyncio.run(_async_scrape_news())
        logger.info(f"Scraped {len(articles)} news articles for terms: {search_terms}.")
        return articles
    except Exception as e:
        logger.error(f"News scraping task failed for terms {search_terms}: {e}")
        raise self.retry(exc=e)

@app.task(bind=True, queue='writer_queue', default_retry_delay=120, max_retries=2)
def write_article_task(self, scraped_content: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Celery task to generate a humanized article from scraped content.
    """
    logger.info(f"Celery task: Writing article for topic: '{scraped_content.get('title', 'N/A')}'")
    writer_agent = HumanizedWriter()
    try:
        # Determine topic and source_type based on scraped_content
        topic = scraped_content.get('title', 'general topic')
        source_url = scraped_content.get('url')
        source_type = scraped_content.get('source_type', 'unknown') # e.g., 'youtube', 'news'

        article_data = writer_agent.generate_humanized_article(topic, source_url, source_type)
        if article_data:
            # The generate_humanized_article now returns a string, not a dict.
            # We need to wrap it in a dict for consistency with subsequent tasks.
            # For now, let's assume the article_data is the content itself.
            # If metadata is needed, it should be generated/handled separately.
            return {"title": topic, "content": article_data, "source_url": source_url, "source_type": source_type}
        else:
            logger.warning(f"Failed to write article for topic: '{topic}'.")
            return None
    except Exception as e:
        logger.error(f"Article writing task failed for topic '{scraped_content.get('title', 'N/A')}': {e}")
        raise self.retry(exc=e)

@app.task(bind=True, queue='publisher_queue', default_retry_delay=180, max_retries=5)
def publish_content_task(self, article_data: Dict[str, Any], publish_immediately: bool = False) -> bool:
    """
    Celery task to publish content.
    """
    logger.info(f"Celery task: Publishing content: '{article_data.get('title', 'N/A')}'")

    async def _async_publish():
        publisher_agent = ContentPublisher()
        try:
            success = await publisher_agent.publish_content(article_data, publish_immediately)
            return success
        except Exception as e:
            logger.error(f"Content publishing failed for '{article_data.get('title', 'N/A')}': {e}")
            raise

    try:
        success = asyncio.run(_async_publish())
        if success:
            logger.info(f"Successfully published content: '{article_data.get('title')}'")
        else:
            logger.warning(f"Failed to publish content: '{article_data.get('title')}'")
        return success
    except Exception as e:
        logger.error(f"Content publishing task failed for '{article_data.get('title', 'N/A')}': {e}")
        raise self.retry(exc=e)

@app.task(bind=True, queue='writer_queue')
def process_scraped_content_for_writing(self, scraped_results: List[List[Dict[str, Any]]]):
    """
    Task to process results from scraping tasks and enqueue writing tasks.
    """
    all_scraped_items = []
    for result_list in scraped_results:
        if result_list:
            all_scraped_items.extend(result_list)

    logger.info(f"Processing {len(all_scraped_items)} scraped items for writing.")

    # Create a group of writing tasks
    writing_tasks = group(write_article_task.s(item) for item in all_scraped_items)
    return writing_tasks() # Execute the group

# Step 2: Process written articles for publishing
@app.task(bind=True, queue='publisher_queue')
def process_written_articles_for_publishing(self, written_articles: List[Optional[Dict[str, Any]]]):
    """
    Task to process results from writing tasks and enqueue publishing tasks.
    """
    valid_articles = [article for article in written_articles if article is not None]
    logger.info(f"Processing {len(valid_articles)} valid articles for publishing.")

    # Create a group of publishing tasks
    publishing_tasks = group(publish_content_task.s(article) for article in valid_articles)
    return publishing_tasks() # Execute the group


class HiveOrchestrator:
    def __init__(self):
        logger.info("Initializing HiveOrchestrator...")
        self.scraper_agent = ContentScraperAgent()
        self.writer_agent = HumanizedWriter()
        self.publisher_agent = ContentPublisher()
        logger.info("HiveOrchestrator initialized with agents.")

    async def start_hive(self, youtube_queries: List[str], news_sources_config: List[str]):
        """
        Starts the automated content generation and publishing pipeline.
        """
        logger.info("HiveOrchestrator: Starting automated content generation pipeline.")
        self.schedule_content_generation(youtube_queries, news_sources_config)
        logger.info("HiveOrchestrator: Pipeline scheduled.")

    def stop_hive(self):
        """
        Gracefully stops the hive operations.
        (For Celery, this typically means stopping workers, which is done externally)
        """
        logger.info("HiveOrchestrator: Stopping hive operations (Celery workers need to be stopped externally).")
        # In a real-world scenario, you might send a shutdown signal to Celery workers
        # or perform cleanup here. For now, it's a placeholder.

    def schedule_content_generation(self, youtube_queries: List[str], news_sources_config: List[str]):
        """
        Schedules the full content generation pipeline using Celery chains and groups.
        """
        logger.info("HiveOrchestrator: Scheduling content generation pipeline via Celery.")

        # Scrape YouTube videos
        youtube_scrape_tasks = [scrape_youtube_task.s(query, max_videos=5) for query in youtube_queries]

        # Scrape news articles (assuming news_sources_config is a list of URLs)
        news_scrape_tasks = [scrape_news_task.s([], [source], max_articles_per_source=2) for source in news_sources_config]

        # Combine all scraping tasks into a group
        all_scrape_tasks = group(youtube_scrape_tasks + news_scrape_tasks)

        # Define the full pipeline chain
        pipeline = chain(
            all_scrape_tasks, # Group of scraping tasks
            process_scraped_content_for_writing.s(), # Process scraped results and fan-out to writing
            process_written_articles_for_publishing.s() # Process written articles and fan-out to publishing
        )

        pipeline.apply_async()
        logger.info("HiveOrchestrator: Full scraping and content generation pipeline initiated.")

    def monitor_agent_health(self):
        """
        Checks the health of all agents. (Placeholder for actual implementation)
        """
        logger.info("HiveOrchestrator: Monitoring agent health (placeholder).")
        # In a real system, this would involve checking Celery worker status,
        # agent-specific health endpoints, etc.
        return {"scraper": "OK", "writer": "OK", "publisher": "OK"}

    def handle_agent_failure(self, agent_name: str):
        """
        Handles failures of individual agents. (Placeholder for actual implementation)
        """
        logger.warning(f"HiveOrchestrator: Handling failure for agent: {agent_name} (placeholder).")
        # This could involve restarting tasks, notifying administrators,
        # or switching to a fallback mechanism.

@app.task(bind=True, queue='default')
def start_scraping_pipeline(self, youtube_queries: List[str], news_sources_config: List[str]):
    """
    Main pipeline task to start the scraping process and chain subsequent tasks.
    This task is intended to be triggered by Celery Beat.
    Now uses HiveOrchestrator to manage the pipeline.
    """
    logger.info("Celery task: Starting the full scraping and content generation pipeline via HiveOrchestrator.")
    orchestrator = HiveOrchestrator()
    orchestrator.schedule_content_generation(youtube_queries, news_sources_config)
    logger.info("Celery task: HiveOrchestrator pipeline scheduled.")
