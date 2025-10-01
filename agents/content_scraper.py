import asyncio
from typing import List, Dict, Any, Optional
from urllib.parse import urlparse, urljoin
import sys

from services.scraper_service import StealthScraper
from database.database_service import db_service
from core.logging_config import log_execution, get_logger

logger = get_logger('scraper')

class ContentScraperAgent:
    """
    An agent specialized in finding trending content (videos and news)
    using the StealthScraper service.
    """
    def __init__(self):
        self.scraper = StealthScraper()
        # _is_initialized is now managed by the Celery task wrapper
        logger.info("ContentScraperAgent initialized.")

    @log_execution(logger_name='scraper')
    async def find_trending_youtube_videos(self, query: str, max_videos: int = 5) -> List[Dict[str, Any]]:
        """
        Finds trending YouTube videos based on a query.
        Returns metadata only, no video downloads.
        """
        # Scraper initialization/closing is handled by the Celery task wrapper
        logger.info(f"🔍 ContentScraperAgent: Iniciando búsqueda de videos de YouTube para la consulta: '{query}' (max_videos: {max_videos})")
        try:
            videos = await self.scraper.scrape_youtube_metadata(query, max_results=max_videos)
            if videos:
                logger.info(f"✅ ContentScraperAgent: Encontrados {len(videos)} videos de YouTube para la consulta '{query}'.")
            else:
                logger.warning(f"⚠️ ContentScraperAgent: No se encontraron videos de YouTube para la consulta '{query}'.")
            logger.info(f"ContentScraperAgent: Retornando {len(videos)} videos.")
            return videos
        except Exception as e:
            logger.error(f"❌ ContentScraperAgent: Error al buscar videos de YouTube para la consulta '{query}': {str(e)}", exc_info=True)
            raise # Re-raise for Celery retry
        finally:
            pass # Scraper initialization/closing is handled by the Celery task wrapper

    @log_execution(logger_name='scraper')
    async def find_popular_news_articles(self, search_terms: List[str], news_sources: List[str], max_articles_per_source: int = 2) -> List[Dict[str, Any]]:
        """
        Finds popular news articles from specified sources based on search terms.
        Implements retry logic and extracts clean title, content, author, date.
        """
        # Scraper initialization/closing is handled by the Celery task wrapper
        all_articles: List[Dict[str, Any]] = []
        logger.info(f"🔍 ContentScraperAgent: Iniciando búsqueda de artículos de noticias con términos: {search_terms} de fuentes: {news_sources}")

        for source_url in news_sources:
            logger.info(f"🔍 ContentScraperAgent: Buscando noticias de la fuente: {source_url}")

            temp_scraper = StealthScraper()
            try:
                await temp_scraper.initialize()
                if not temp_scraper._is_initialized:
                    logger.error(f"❌ ContentScraperAgent: Falló la inicialización del scraper temporal para: {source_url}, saltando.")
                    continue

                context, page = await temp_scraper._create_stealth_context_and_page()
                if not await temp_scraper._human_like_navigation(page, source_url):
                    logger.warning(f"Could not navigate to news source: {source_url}")
                    await page.close()
                    await context.close()
                    continue

                article_links = await page.evaluate("""
                    () => {
                        const links = Array.from(document.querySelectorAll('a[href]'));
                        const uniqueLinks = new Set();
                        const filteredLinks = [];
                        for (const link of links) {
                            const href = link.href;
                            if (href && !href.startsWith('#') && !uniqueLinks.has(href) &&
                                (href.includes('/article/') || href.includes('/news/') || href.includes('/story/') ||
                                 href.match(/\\/\\d{4}\\/\\d{2}\\/\\d{2}\\//) ||
                                 href.match(/\\/post\\//) || href.match(/\\/blog\\//))) {
                                uniqueLinks.add(href);
                                filteredLinks.push(href);
                            }
                        }
                        return filteredLinks.slice(0, 10);
                    }
                """)

                await page.close()
                await context.close()

                articles_from_source = 0
                for link in article_links:
                    if articles_from_source >= max_articles_per_source:
                        logger.info(f"ContentScraperAgent: Alcanzado el máximo de artículos ({max_articles_per_source}) para la fuente {source_url}.")
                        break

                    if any(term.lower() in link.lower() for term in search_terms):
                        logger.info(f"🔍 ContentScraperAgent: Extrayendo contenido del artículo del enlace: {link}")
                        article_data = await self.scraper.scrape_news_article(link)

                        if article_data:
                            if any(term.lower() in article_data.get('title', '').lower() for term in search_terms) or \
                               any(term.lower() in article_data.get('content', '').lower() for term in search_terms):
                                all_articles.append(article_data)
                                articles_from_source += 1
                                logger.info(f"✅ ContentScraperAgent: Artículo extraído y coincidente: '{article_data.get('title')}'")
                            else:
                                logger.debug(f"⚠️ ContentScraperAgent: Artículo no coincide con los términos de búsqueda en título/contenido: {link}")
                        else:
                            logger.warning(f"❌ ContentScraperAgent: Falló la extracción del artículo del enlace: {link}")
                    else:
                        logger.debug(f"ContentScraperAgent: Saltando enlace ya que no coincide con los términos de búsqueda en la URL: {link}")

            except Exception as e:
                logger.error(f"Error processing news source {source_url}: {str(e)}", exc_info=True)
                raise # Re-raise for Celery retry
            finally:
                await temp_scraper.close()

        logger.info(f"✅ ContentScraperAgent: Encontrados {len(all_articles)} artículos de noticias en total.")
        return all_articles

# Removed example usage and venv check as orchestration will handle execution
