from celery import Celery
import os

# Default Redis URL for local development
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')

app = Celery('orchestrator',
             broker=REDIS_URL,
             backend=REDIS_URL,
             include=['tasks.orchestrator']) # Include orchestrator tasks

app.conf.update(
    task_serializer='json',
    result_serializer='json',
    accept_content=['json'],
    timezone='America/New_York', # Or your desired timezone
    enable_utc=True,
    task_acks_late=True, # Acknowledge tasks after they're done
    worker_prefetch_multiplier=1, # Only fetch one task at a time
    task_default_retry_delay=300, # 5 minutes
    task_max_retries=5,
    broker_connection_retry_on_startup=True,
    # Define queues for prioritization
    task_queues={
        'scraper_queue': {'exchange': 'scraper', 'routing_key': 'scraper'},
        'writer_queue': {'exchange': 'writer', 'routing_key': 'writer'},
        'publisher_queue': {'exchange': 'publisher', 'routing_key': 'publisher'},
    },
    task_default_queue='default',
    task_default_exchange='default',
    task_default_routing_key='default',
    # Celery Beat Schedule (for periodic tasks)
    beat_schedule={
        'run-scraping-pipeline-every-hour': {
            'task': 'tasks.orchestrator.start_scraping_pipeline',
            'schedule': 3600.0, # Run every hour (in seconds)
            'args': (["AI trends", "latest tech news"], ["https://www.bbc.com/news/technology", "https://www.nytimes.com/section/technology"]),
            'options': {'queue': 'scraper_queue'}
        },
    },
)

if __name__ == '__main__':
    app.start()
