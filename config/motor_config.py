import os
from typing import Dict, Any, List
from dotenv import load_dotenv

load_dotenv() # Cargar variables de entorno desde .env

class MotorConfig:
    # Redis/Upstash
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    UPSTASH_REDIS_URL: str = os.getenv("UPSTASH_REDIS_URL", REDIS_URL) # Assuming UPSTASH_REDIS_URL defaults to REDIS_URL if not set
    REDIS_HOST: str = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", 6379))

    # Supabase
    SUPABASE_URL: str = os.getenv("SUPABASE_URL")
    SUPABASE_KEY: str = os.getenv("SUPABASE_KEY")

    # AI API Keys (prefixes for numbered keys)
    GROQ_API_KEY_PREFIX: str = "GROQ_API_KEY"
    COHERE_API_KEY_PREFIX: str = "COHERE_API_KEY"
    HUGGINGFACE_API_KEY_PREFIX: str = "HUGGINGFACE_API_KEY"
    GEMINI_API_KEY_PREFIX: str = "GEMINI_API_KEY"

    # AI Provider Configurations (from config/ai_config.py)
    AI_PROVIDER_CONFIG: Dict[str, Any] = {
        "Groq": {
            "url": "https://api.groq.com/openai/v1/chat/completions",
            "model": "llama-3.1-8b-instant",
            "keys_env": "GROQ_API_KEY"
        },
        "Cohere": {
            "url": "https://api.cohere.ai/v1/chat",
            "model": "command-r-08-2024",
            "keys_env": "COHERE_API_KEY"
        },
        "HuggingFace": {
            "url": "https://api-inference.huggingface.co/models",
            "model": "mistralai/Mistral-7B-Instruct-v0.2",
            "keys_env": "HUGGINGFACE_API_KEY"
        },
        "Gemini": {
            "url": "https://generativelanguage.googleapis.com/v1beta/models",
            "model": "gemini-1.5-flash-latest",
            "keys_env": "GEMINI_API_KEY"
        }
    }

    # Celery Configuration (from core/celery_config.py)
    CELERY_BROKER_URL: str = REDIS_URL
    CELERY_RESULT_BACKEND: str = REDIS_URL
    CELERY_INCLUDE: List[str] = ['tasks.orchestrator'] # This might need to be dynamic later

    CELERY_TASK_SERIALIZER: str = 'json'
    CELERY_RESULT_SERIALIZER: str = 'json'
    CELERY_ACCEPT_CONTENT: List[str] = ['json']
    CELERY_TIMEZONE: str = 'UTC'
    CELERY_ENABLE_UTC: bool = True
    CELERY_TASK_ACKS_LATE: bool = True
    CELERY_WORKER_PREFETCH_MULTIPLIER: int = 1
    CELERY_TASK_DEFAULT_RETRY_DELAY: int = 300
    CELERY_TASK_MAX_RETRIES: int = 5
    CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP: bool = True

    CELERY_TASK_QUEUES: Dict[str, Any] = {
        'scraper_queue': {'exchange': 'scraper', 'routing_key': 'scraper'},
        'writer_queue': {'exchange': 'writer', 'routing_key': 'writer'},
        'publisher_queue': {'exchange': 'publisher', 'routing_key': 'publisher'},
        'default': {'exchange': 'default', 'routing_key': 'default'},
    }
    CELERY_TASK_DEFAULT_QUEUE: str = 'default'
    CELERY_TASK_DEFAULT_EXCHANGE: str = 'default'
    CELERY_TASK_DEFAULT_ROUTING_KEY: str = 'default'

    CELERY_BEAT_SCHEDULE: Dict[str, Any] = {
        'run-scraping-pipeline-every-hour': {
            'task': 'tasks.orchestrator.start_scraping_pipeline',
            'schedule': 3600.0,
            'args': (),
            'options': {'queue': 'default'}
        },
    }

    # Circuit Breaker Configuration (from core/circuit_breaker.py)
    CIRCUIT_BREAKER_ENABLED: bool = os.getenv('CIRCUIT_BREAKER_ENABLED', 'true').lower() == 'true'
    CIRCUIT_BREAKER_FAILURE_THRESHOLD: int = int(os.getenv('CIRCUIT_BREAKER_FAILURE_THRESHOLD', '5'))
    CIRCUIT_BREAKER_TIMEOUT_SECONDS: int = int(os.getenv('CIRCUIT_BREAKER_TIMEOUT_SECONDS', '60'))
    CIRCUIT_BREAKER_SUCCESS_THRESHOLD: int = int(os.getenv('CIRCUIT_BREAKER_SUCCESS_THRESHOLD', '3'))

    # Logging Configuration (from core/logging_config.py)
    LOG_LEVEL: str = os.getenv('LOG_LEVEL', 'INFO').upper()
    LOG_FORMAT: str = os.getenv('LOG_FORMAT', 'json')
    LOG_ROTATION_SIZE_MB: int = int(os.getenv('LOG_ROTATION_SIZE_MB', '10'))
    LOG_BACKUP_COUNT: int = int(os.getenv('LOG_BACKUP_COUNT', '5'))

    @classmethod
    def validate(cls):
        """Validación estricta de configuración"""
        import logging
        logger = logging.getLogger(__name__)

        errors = []

        # 1. VALIDAR SUPABASE (CRÍTICO)
        if not cls.SUPABASE_URL:
            errors.append("❌ SUPABASE_URL faltante")
            logger.error("   → Obtener en: https://supabase.com > Settings > API")
        elif not cls.SUPABASE_URL.startswith('https://'):
            errors.append("❌ SUPABASE_URL debe empezar con https://")

        if not cls.SUPABASE_KEY:
            errors.append("❌ SUPABASE_KEY faltante")
            logger.error("   → Obtener en: https://supabase.com > Settings > API > anon/public key")

        # 2. VALIDAR REDIS (CRÍTICO)
        if not cls.REDIS_URL and not cls.UPSTASH_REDIS_URL:
            errors.append("❌ Falta REDIS_URL o UPSTASH_REDIS_URL")
            logger.error("   → Redis local: redis://localhost:6379/0")
            logger.error("   → O Upstash: https://upstash.com (gratis)")

        # 3. VALIDAR AL MENOS 1 API DE IA (OPCIONAL PERO RECOMENDADO)
        has_ai_api = any([
            any(os.getenv(f"{cls.GEMINI_API_KEY_PREFIX}_{i}") for i in range(1, 13)),
            any(os.getenv(f"{cls.COHERE_API_KEY_PREFIX}_{i}") for i in range(1, 13)),
            any(os.getenv(f"{cls.GROQ_API_KEY_PREFIX}_{i}") for i in range(1, 13)),
            any(os.getenv(f"{cls.HUGGINGFACE_API_KEY_PREFIX}_{i}") for i in range(1, 13))
        ])

        if not has_ai_api:
            logger.warning("⚠️  No hay APIs de IA configuradas")
            logger.warning("   → Al menos configura 1: Gemini, Cohere, Groq o HuggingFace")

        # 4. SI HAY ERRORES CRÍTICOS, DETENER
        if errors:
            logger.error("\n" + "="*60)
            logger.error("🚨 CONFIGURACIÓN INCOMPLETA")
            logger.error("="*60)
            for error in errors:
                logger.error(error)
            logger.error("\n📝 Pasos para corregir:")
            logger.error("1. Copia .env.example a .env")
            logger.error("2. Completa las variables requeridas")
            logger.error("3. Ejecuta de nuevo\n")
            raise ValueError(f"Faltan {len(errors)} configuraciones críticas")

        logger.info("✅ Configuración validada correctamente")
        return True

def get_motor_config() -> MotorConfig:
    config = MotorConfig()
    config.validate()
    return config
