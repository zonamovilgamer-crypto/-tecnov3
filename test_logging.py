import asyncio
import os
import uuid
from typing import Any, Dict

from core.context_logger import ContextLogger
from structlog.contextvars import bind_contextvars, clear_contextvars
import structlog.contextvars

# Set environment variables for logging configuration (for testing purposes)
os.environ["LOG_LEVEL"] = "DEBUG"
os.environ["LOG_DIR"] = "logs"
os.environ["LOG_FILE_MAX_BYTES"] = "10485760"
os.environ["LOG_FILE_BACKUP_COUNT"] = "5"
os.environ["ENV"] = "development" # To see console output in a more readable format

# Initialize component-specific loggers
scraper_logger = ContextLogger("scraper")
writer_logger = ContextLogger("writer")
publisher_logger = ContextLogger("publisher")
celery_logger = ContextLogger("celery")

@scraper_logger.log_execution
async def simulate_scraper_task(query: str, user_id: str) -> Dict[str, Any]:
    """Simulates a scraping operation with context."""
    with scraper_logger.log_context(user_id=user_id, operation="youtube_scrape", query=query):
        scraper_logger.logger.info("Starting YouTube video search.")
        await asyncio.sleep(0.5) # Simulate I/O
        if "error" in query:
            raise ValueError("Simulated scraping error")
        scraper_logger.logger.info("Finished YouTube video search.", videos_found=5)
        return {"status": "success", "videos": 5}

@writer_logger.log_execution
def simulate_writer_task(article_topic: str, trace_id: str) -> Dict[str, Any]:
    """Simulates an article writing operation with context."""
    # trace_id is already bound by the decorator if not present, but we can explicitly bind/override
    with writer_logger.log_context(article_topic=article_topic, trace_id=trace_id):
        writer_logger.logger.info("Starting article generation.")
        time.sleep(0.3) # Simulate CPU work
        if "fail" in article_topic:
            raise RuntimeError("Simulated writing failure")
        writer_logger.logger.info("Article generation complete.", word_count=1200)
        return {"status": "success", "word_count": 1200}

@publisher_logger.log_execution
async def simulate_publisher_task(article_id: str, user_id: str) -> bool:
    """Simulates publishing an article."""
    async with publisher_logger.async_log_context(article_id=article_id, user_id=user_id, operation="publish"):
        publisher_logger.logger.info("Attempting to publish article.")
        await asyncio.sleep(0.2) # Simulate network delay
        if "fail" in article_id:
            publisher_logger.logger.error("Failed to publish article.", reason="network_issue")
            return False
        publisher_logger.logger.info("Article published successfully.")
        return True

@celery_logger.log_execution
async def main_orchestrator_task(main_user_id: str):
    """Main task orchestrator demonstrating cross-component logging."""
    # Bind a global trace_id and user_id for the entire orchestration flow
    bind_contextvars(trace_id=str(uuid.uuid4()), user_id=main_user_id)
    celery_logger.logger.info("Orchestrator task started.")

    try:
        # Simulate scraper
        scraper_result = await simulate_scraper_task("trending tech", main_user_id)
        celery_logger.logger.info("Scraper task completed.", result=scraper_result)

        # Simulate writer
        writer_result = simulate_writer_task("The Future of AI", structlog.contextvars.get_context().get("trace_id"))
        celery_logger.logger.info("Writer task completed.", result=writer_result)

        # Simulate publisher
        publish_success = await simulate_publisher_task("article-123", main_user_id)
        celery_logger.logger.info("Publisher task completed.", success=publish_success)

        # Simulate an error scenario
        try:
            await simulate_scraper_task("error query", main_user_id)
        except ValueError:
            celery_logger.logger.warning("Expected error caught during scraper simulation.")

        try:
            simulate_writer_task("fail topic", structlog.contextvars.get_context().get("trace_id"))
        except RuntimeError:
            celery_logger.logger.warning("Expected error caught during writer simulation.")

    except Exception as e:
        celery_logger.logger.critical("An unhandled error occurred in orchestrator.", error=str(e), exc_info=True)
    finally:
        celery_logger.logger.info("Orchestrator task finished.")
        clear_contextvars() # Clear context at the end of the main task

if __name__ == "__main__":
    import time
    asyncio.run(main_orchestrator_task("orchestrator-user-001"))
    print("\nCheck the 'logs' directory for generated log files.")
