import asyncio
from database.database_service import db_service
import os
from dotenv import load_dotenv
from core.logging_config import get_logger

# Cargar variables de entorno desde .env
load_dotenv()

logger = get_logger('test_supabase')

async def test():
    logger.info("Iniciando test de Supabase...")

    # Asegurarse de que el cliente de Supabase esté inicializado
    if not db_service.is_connected():
        logger.warning("Supabase client not connected. Attempting to re-initialize.")
        try:
            db_service._initialize_client()
            if not db_service.is_connected():
                logger.error("Failed to re-initialize Supabase client. Aborting test.")
                return
            logger.info("Supabase client re-initialized successfully.")
        except Exception as e:
            logger.error(f"Error during Supabase client re-initialization: {e}")
            return

    # Test de escritura directa de video
    test_video = {
        "youtube_id": f"TEST_VIDEO_{int(time.time())}",
        "title": "Test Video from test_supabase.py",
        "description": "This is a test description for a video.",
        "query_used": "test_query",
        "thumbnail_url": "http://example.com/thumb.jpg",
        "channel_title": "Test Channel",
        "published_at": "2023-01-01T12:00:00Z",
        "duration": "PT10M30S",
        "view_count": 100,
        "embed_url": "http://example.com/embed"
    }

    logger.info(f"Intentando guardar video de prueba: {test_video.get('title')}")
    try:
        result_video = await db_service.save_video(test_video)
        if result_video:
            logger.info(f"✅ Video de prueba guardado exitosamente. ID: {result_video.get('id')}")
        else:
            logger.error("❌ Falló el guardado del video de prueba. Resultado nulo.")
    except Exception as e:
        logger.error(f"❌ Error al guardar video de prueba: {e}", exc_info=True)

    # Test de escritura directa de artículo
    test_article = {
        "title": f"Test Article from test_supabase.py {int(time.time())}",
        "content": "This is the content of a test article.",
        "excerpt": "Test excerpt...",
        "slug": f"test-article-{int(time.time())}",
        "status": "draft",
        "source_type": "test",
        "source_url": "http://example.com/test-article",
        "author": "Test Author",
        "word_count": 50,
        "reading_time": 1
    }

    logger.info(f"Intentando guardar artículo de prueba: {test_article.get('title')}")
    try:
        result_article = await db_service.save_article(test_article)
        if result_article:
            logger.info(f"✅ Artículo de prueba guardado exitosamente. ID: {result_article.get('id')}")
            # Test update status
            logger.info(f"Intentando actualizar estado del artículo de prueba ID: {result_article.get('id')} a 'published'")
            updated_article = await db_service.update_article_status(result_article.get('id'), "published")
            if updated_article:
                logger.info(f"✅ Estado del artículo de prueba actualizado a 'published' exitosamente.")
            else:
                logger.error("❌ Falló la actualización del estado del artículo de prueba.")
        else:
            logger.error("❌ Falló el guardado del artículo de prueba. Resultado nulo.")
    except Exception as e:
        logger.error(f"❌ Error al guardar artículo de prueba: {e}", exc_info=True)

    logger.info("Test de Supabase finalizado.")

if __name__ == "__main__":
    import time
    asyncio.run(test())
