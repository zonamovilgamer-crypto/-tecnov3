import asyncio
from celery import Celery, chain, group
from celery.signals import task_postrun, task_prerun
from typing import List, Dict, Any, Optional

from core.celery_config import app
from agents.content_scraper import ContentScraperAgent
from agents.content_writer import HumanizedWriter
from agents.content_publisher import ContentPublisher
from database.database_service import db_service
from core.logging_config import log_execution, get_logger

logger = get_logger('celery')

# Initialize agents
scraper_agent = ContentScraperAgent()
writer_agent = HumanizedWriter()
publisher_agent = ContentPublisher()

# Celery tasks definitions

@app.task(bind=True, queue='scraper_queue', default_retry_delay=60, max_retries=3)
@log_execution(logger_name='celery')
def scrape_youtube_task(self, query: str, max_videos: int = 5) -> List[Dict[str, Any]]:
    """
    Celery task to scrape YouTube video metadata and save it to the database.
    """
    logger.info(f"📊 Datos recibidos para procesar (YouTube scraping): query='{query}', max_videos={max_videos} (task_id: {self.request.id})")

    async def _async_scrape():
        videos = await scraper_agent.find_trending_youtube_videos(query, max_videos)

        if db_service.is_connected():
            for video_data in videos:
                await db_service.save_video(video_data)
            logger.info(f"Saved {len(videos)} YouTube videos to database for query '{query}' (task_id: {self.request.id}).")
        else:
            logger.warning(f"Supabase not connected. Skipping saving YouTube video metadata (task_id: {self.request.id}).")

        return videos

    try:
        videos = asyncio.run(_async_scrape())
        logger.info(f"✅ Tarea scrape_youtube_task completada, retornando {len(videos)} videos (task_id: {self.request.id}).")
        return videos
    except Exception as e:
        logger.error(f"❌ YouTube scraping task failed for query '{query}': {e} (task_id: {self.request.id})", exc_info=True)
        raise self.retry(exc=e)

@app.task(bind=True, queue='scraper_queue', default_retry_delay=60, max_retries=3)
@log_execution(logger_name='celery')
def scrape_news_task(self, search_terms: List[str], news_sources: List[str], max_articles_per_source: int = 2) -> List[Dict[str, Any]]:
    """
    Celery task to scrape news articles and save them to the database.
    """
    logger.info(f"📊 Datos recibidos para procesar (News scraping): terms={search_terms}, sources={news_sources} (task_id: {self.request.id})")

    async def _async_scrape_news():
        articles = await scraper_agent.find_popular_news_articles(search_terms, news_sources, max_articles_per_source)

        # Save scraped articles to the database (this is for the *original* scraped article metadata)
        if db_service.is_connected():
            for article_data in articles:
                # Note: This saves the *scraped* article metadata, not the humanized one.
                # The humanized article will be saved by write_article_task.
                await db_service.save_article(article_data)
            logger.info(f"Saved {len(articles)} *scraped* news articles to database for terms: {search_terms} (task_id: {self.request.id}).")
        else:
            logger.warning(f"Supabase not connected. Skipping saving *scraped* news article data (task_id: {self.request.id}).")

        return articles

    try:
        articles = asyncio.run(_async_scrape_news())
        logger.info(f"✅ Tarea scrape_news_task completada, retornando {len(articles)} articles (task_id: {self.request.id}).")
        return articles
    except Exception as e:
        logger.error(f"❌ News scraping task failed for terms {search_terms}: {e} (task_id: {self.request.id})", exc_info=True)
        raise self.retry(exc=e)

@app.task(bind=True, queue='writer_queue', default_retry_delay=120, max_retries=2)
@log_execution(logger_name='celery')
def write_article_task(self, scraped_content: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Celery task to generate a humanized article from scraped content.
    """
    topic = scraped_content.get('title', 'N/A')
    logger.info(f"📊 Datos recibidos para procesar (write_article_task): topic='{topic}' (task_id: {self.request.id})")

    try:
        topic = scraped_content.get('title', 'general topic')
        source_url = scraped_content.get('url')
        source_type = scraped_content.get('source_type', 'unknown')

        generated_content = asyncio.run(writer_agent.generate_humanized_article(topic, source_url, source_type))

        if generated_content:
            # Construct the article data to be saved and passed to the next task
            humanized_article_data = {
                "title": topic,
                "content": generated_content,
                "source_url": source_url,
                "source_type": source_type,
                "status": "generated" # Initial status
            }

            # Save the humanized article to the database
            if db_service.is_connected():
                async def _async_save_article():
                    return await db_service.save_article(humanized_article_data)

                saved_article = asyncio.run(_async_save_article())

                if saved_article:
                    logger.info(f"✅ Humanized article saved to Supabase, ID: {saved_article.get('id')} (task_id: {self.request.id}).")
                    humanized_article_data['id'] = saved_article.get('id')
                else:
                    logger.warning(f"⚠️ Failed to save humanized article to Supabase for topic: '{topic}' (task_id: {self.request.id}).")
            else:
                logger.warning(f"Supabase not connected. Skipping saving humanized article for topic: '{topic}' (task_id: {self.request.id}).")

            logger.info(f"✅ Tarea write_article_task completada, retornando humanized article for topic: '{topic}' (task_id: {self.request.id}).")
            return humanized_article_data
        else:
            logger.warning(f"Failed to generate article content for topic: '{topic}' (task_id: {self.request.id}).")
            return None
    except Exception as e:
        logger.error(f"❌ Article writing task failed for topic '{topic}': {e} (task_id: {self.request.id})", exc_info=True)
        raise self.retry(exc=e)

@app.task(bind=True, queue='publisher_queue', default_retry_delay=180, max_retries=5)
@log_execution(logger_name='celery')
def publish_content_task(self, article_data: Dict[str, Any], publish_immediately: bool = False) -> bool:
    """
    Celery task to publish content.
    """
    title = article_data.get('title', 'N/A')
    logger.info(f"📊 Datos recibidos para procesar (publish_content_task): title='{title}' (task_id: {self.request.id})")

    async def _async_publish():
        try:
            success = await publisher_agent.publish_content(article_data, publish_immediately)
            return success
        except Exception as e:
            logger.error(f"❌ Content publishing failed for '{title}': {e} (task_id: {self.request.id})", exc_info=True)
            raise

    try:
        success = asyncio.run(_async_publish())
        if success:
            logger.info(f"✅ Successfully published content: '{title}' (task_id: {self.request.id})")
            # Optionally update status in DB after successful publication
            if db_service.is_connected() and article_data.get('id'):
                async def _async_update_article_status():
                    return await db_service.update_article_status(article_data['id'], "published")

                asyncio.run(_async_update_article_status())
                logger.info(f"✅ Article status updated to 'published' for ID: {article_data['id']} (task_id: {self.request.id}).")
        else:
            logger.warning(f"⚠️ Failed to publish content: '{title}' (task_id: {self.request.id})")
        logger.info(f"✅ Tarea publish_content_task completada, retornando: {success} (task_id: {self.request.id}).")
        return success
    except Exception as e:
        logger.error(f"❌ Content publishing task failed for '{title}': {e} (task_id: {self.request.id})", exc_info=True)
        raise self.retry(exc=e)

@app.task(bind=True, queue='writer_queue')
@log_execution(logger_name='celery')
def process_scraped_content_for_writing(self, scraped_results: List[List[Dict[str, Any]]]):
    """
    Task to process results from scraping tasks and enqueue writing tasks.
    """
    all_scraped_items = []
    for result_list in scraped_results:
        if result_list:
            all_scraped_items.extend(result_list)

    logger.info(f"📊 Datos recibidos para procesar (process_scraped_content_for_writing): {len(all_scraped_items)} items (task_id: {self.request.id}).")

    writing_tasks = group(write_article_task.s(item) for item in all_scraped_items)
    result = writing_tasks()
    logger.info(f"✅ Tarea process_scraped_content_for_writing completada, retornando Celery group result (task_id: {self.request.id}).")
    return result

# Step 2: Process written articles for publishing
@app.task(bind=True, queue='publisher_queue')
@log_execution(logger_name='celery')
def process_written_articles_for_publishing(self, written_articles: List[Optional[Dict[str, Any]]]):
    """
    Task to process results from writing tasks and enqueue publishing tasks.
    """
    valid_articles = [article for article in written_articles if article is not None]
    logger.info(f"📊 Datos recibidos para procesar (process_written_articles_for_publishing): {len(valid_articles)} items (task_id: {self.request.id}).")

    publishing_tasks = group(publish_content_task.s(article) for article in valid_articles)
    result = publishing_tasks()
    logger.info(f"✅ Tarea process_written_articles_for_publishing completada, retornando Celery group result (task_id: {self.request.id}).")
    return result


class HiveOrchestrator:
    """
    Orchestrates the entire content generation and publishing pipeline using Celery.
    """
    def __init__(self):
        logger.info("Initializing HiveOrchestrator...")
        self.scraper_agent = ContentScraperAgent()
        self.writer_agent = HumanizedWriter()
        self.publisher_agent = ContentPublisher()
        logger.info("HiveOrchestrator initialized with agents.")

    @log_execution(logger_name='celery')
    async def start_hive(self, youtube_queries: List[str], news_sources_config: List[str]):
        """
        Starts the automated content generation and publishing pipeline.
        """
        logger.info("HiveOrchestrator: Starting automated content generation pipeline.")
        self.schedule_content_generation(youtube_queries, news_sources_config)
        logger.info("HiveOrchestrator: Pipeline scheduled.")

    @log_execution(logger_name='celery')
    def stop_hive(self):
        """
        Gracefully stops the hive operations.
        (For Celery, this typically means stopping workers, which is done externally)
        """
        logger.info("HiveOrchestrator: Stopping hive operations (Celery workers need to be stopped externally).")
        # In a real-world scenario, you might send a shutdown signal to Celery workers
        # or perform cleanup here. For now, it's a placeholder.

    @log_execution(logger_name='celery')
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

    @log_execution(logger_name='celery')
    def monitor_agent_health(self):
        """
        Checks the health of all agents. (Placeholder for actual implementation)
        """
        logger.info("HiveOrchestrator: Monitoring agent health (placeholder).")
        # In a real system, this would involve checking Celery worker status,
        # agent-specific health endpoints, etc.
        return {"scraper": "OK", "writer": "OK", "publisher": "OK"}

    @log_execution(logger_name='celery')
    def handle_agent_failure(self, agent_name: str):
        """
        Handles failures of individual agents. (Placeholder for actual implementation)
        """
        logger.warning(f"HiveOrchestrator: Handling failure for agent: {agent_name} (placeholder).")
        # This could involve restarting tasks, notifying administrators,
        # or switching to a fallback mechanism.

@app.task(bind=True, queue='default')
@log_execution(logger_name='celery')
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
