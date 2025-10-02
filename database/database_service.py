import logging
from typing import Dict, Any, List, Optional

# Import logging from core.logging_config
from core.logging_config import get_logger, log_execution
logger = get_logger('database')

# Import circuit breaker
from core.circuit_breaker import with_circuit_breaker, CircuitBreakerOpenException

# Import the global Supabase client from the new provider
from providers.db_provider import supabase as global_supabase_client

class DatabaseService:
    """
    Servicio para interactuar con Supabase
    """
    def __init__(self):
        self.client = global_supabase_client
        logger.info(f"Supabase client loaded from provider: {self.client is not None}")

    def is_connected(self) -> bool:
        """Verifica si la conexión a Supabase está activa"""
        return self.client is not None

    @log_execution(logger_name='database')
    @with_circuit_breaker(name="supabase_save_article", expected_exception=CircuitBreakerOpenException)
    async def save_article(self, article_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Guarda un artículo en la tabla 'articles'
        """
        if not self.is_connected():
            logger.error("Cannot save article - Supabase not connected")
            return None

        try:
            logger.info(f"💾 Intentando guardar en Supabase (articles): {article_data}")
            response = self.client.table('articles').insert(article_data).execute()
            if response.data:
                logger.info(f"✅ Guardado exitoso (articles), ID: {response.data[0].get('id')}")
                return response.data[0]
            else:
                logger.warning(f"⚠️ Guardado de artículo no retornó datos: {article_data.get('title')}")
                return None
        except Exception as e:
            logger.error(f"❌ Error al guardar artículo en Supabase: {e}")
            raise # Re-raise to trigger circuit breaker

    @log_execution(logger_name='database')
    @with_circuit_breaker(name="supabase_save_video", expected_exception=CircuitBreakerOpenException)
    async def save_video(self, video_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Guarda metadata de video en la tabla 'videos'
        """
        if not self.is_connected():
            logger.error("Cannot save video - Supabase not connected")
            return None

        try:
            logger.info(f"💾 Intentando guardar en Supabase (videos): {video_data}")
            response = self.client.table('videos').insert(video_data).execute()
            if response.data:
                logger.info(f"✅ Guardado exitoso (videos), ID: {response.data[0].get('id')}")
                return response.data[0]
            else:
                logger.warning(f"⚠️ Guardado de video no retornó datos: {video_data.get('title')}")
                return None
        except Exception as e:
            logger.error(f"❌ Error al guardar video en Supabase: {e}")
            raise # Re-raise to trigger circuit breaker

    @log_execution(logger_name='database')
    @with_circuit_breaker(name="supabase_update_article_status", expected_exception=CircuitBreakerOpenException)
    async def update_article_status(self, article_id: str, status: str) -> Optional[Dict[str, Any]]:
        """
        Actualiza el estado de un artículo en la tabla 'articles'
        """
        if not self.is_connected():
            logger.error("Cannot update article - Supabase not connected")
            return None

        try:
            response = self.client.table('articles').update({"status": status}).eq("id", article_id).execute()
            logger.info(f"✅ Article status updated to '{status}' for ID: {article_id}")
            return response.data[0] if response.data else None
        except Exception as e:
            logger.error(f"❌ Error updating article status: {e}")
            raise # Re-raise to trigger circuit breaker

# Instancia global para usar en todo el proyecto
db_service = DatabaseService()
