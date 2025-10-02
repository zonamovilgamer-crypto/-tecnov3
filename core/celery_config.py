from celery import Celery
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.motor_config import get_motor_config
from providers.cache_provider import redis

config = get_motor_config()

app = Celery('orchestrator',
             broker=config.CELERY_BROKER_URL,
             backend=config.CELERY_RESULT_BACKEND, # Restaurar el backend original
             include=config.CELERY_INCLUDE)

app.conf.update(
    task_serializer=config.CELERY_TASK_SERIALIZER,
    result_serializer=config.CELERY_RESULT_SERIALIZER,
    accept_content=config.CELERY_ACCEPT_CONTENT,
    timezone=config.CELERY_TIMEZONE,
    enable_utc=config.CELERY_ENABLE_UTC,
    task_acks_late=config.CELERY_TASK_ACKS_LATE,
    worker_prefetch_multiplier=config.CELERY_WORKER_PREFETCH_MULTIPLIER,
    task_default_retry_delay=config.CELERY_TASK_DEFAULT_RETRY_DELAY,
    task_max_retries=config.CELERY_TASK_MAX_RETRIES,
    broker_connection_retry_on_startup=config.CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP,

    # Configuración para manejo de resultados y errores
    task_ignore_result=True,  # Ignorar resultados de tareas por defecto
    task_store_errors_even_if_ignored=True,  # Almacenar errores incluso si los resultados son ignorados

    # Queues para priorización
    task_queues=config.CELERY_TASK_QUEUES,
    task_default_queue=config.CELERY_TASK_DEFAULT_QUEUE,
    task_default_exchange=config.CELERY_TASK_DEFAULT_EXCHANGE,
    task_default_routing_key=config.CELERY_TASK_DEFAULT_ROUTING_KEY,

    # ✅ CELERY BEAT CONFIGURADO PARA 1 HORA
    beat_schedule=config.CELERY_BEAT_SCHEDULE,
)

if __name__ == '__main__':
    app.start()
