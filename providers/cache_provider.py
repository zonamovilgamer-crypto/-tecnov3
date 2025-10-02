from redis import Redis
from config.motor_config import get_motor_config

config = get_motor_config()

def get_redis_client() -> Redis:
    """Retorna cliente inicializado de Redis"""
    return Redis.from_url(config.REDIS_URL, decode_responses=True)

# Instancia global
redis = get_redis_client()
