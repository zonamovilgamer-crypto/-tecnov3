from celery import Celery

# ✅ URL CORRECTA de Redis Cloud (ya verificada)
REDIS_URL = 'redis://default:59UGKSDD5Zh6SyBBpnEZXdu72Z64gd4U@redis-12790.c325.us-east-1-4.ec2.redns.redis-cloud.com:12790'

app = Celery('orchestrator',
             broker=REDIS_URL,
             backend=REDIS_URL,
             include=['tasks.orchestrator'])

app.conf.update(
    task_serializer='json',
    result_serializer='json',
    accept_content=['json'],
    timezone='UTC',
    enable_utc=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_default_retry_delay=300,
    task_max_retries=5,
    broker_connection_retry_on_startup=True,

    # Queues para priorización
    task_queues={
        'scraper_queue': {'exchange': 'scraper', 'routing_key': 'scraper'},
        'writer_queue': {'exchange': 'writer', 'routing_key': 'writer'},
        'publisher_queue': {'exchange': 'publisher', 'routing_key': 'publisher'},
        'default': {'exchange': 'default', 'routing_key': 'default'},
    },
    task_default_queue='default',
    task_default_exchange='default',
    task_default_routing_key='default',

    # ✅ CELERY BEAT CONFIGURADO PARA 1 HORA
    beat_schedule={
        'run-scraping-pipeline-every-hour': {
            'task': 'tasks.orchestrator.start_scraping_pipeline',
            'schedule': 3600.0,  # 1 hora = 3600 segundos
            'args': (),  # Sin parámetros
            'options': {'queue': 'default'}
        },
    },
)

if __name__ == '__main__':
    app.start()
