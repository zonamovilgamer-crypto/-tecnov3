import asyncio
from typing import List, Dict, Any, Optional
from urllib.parse import urlparse, urljoin
import sys

from services.scraper_service import StealthScraper
from core.celery_config import app # Import the Celery app
from database.database_service import db_service
from core.context_logger import ContextLogger

scraper_context_logger = ContextLogger("scraper")

class ContentScraperAgent:
    """
    An agent specialized in finding trending content (videos and news)
    using the StealthScraper service.
    """
    def __init__(self):
        self.scraper = StealthScraper()
        self.context_logger = scraper_context_logger
        # _is_initialized is now managed by the Celery task wrapper
        self.context_logger.logger.info("ContentScraperAgent initialized.")

    @scraper_context_logger.log_execution
    async def find_trending_youtube_videos(self, query: str, max_videos: int = 5) -> List[Dict[str, Any]]:
        """
        Finds trending YouTube videos based on a query.
        Returns metadata only, no video downloads.
        """
        # Scraper initialization/closing is handled by the Celery task wrapper
        self.context_logger.logger.info("Agent searching for trending YouTube videos", query=query)
        try:
            # Ensure scraper is initialized for this call
            await self.scraper.initialize()
            videos = await self.scraper.scrape_youtube_metadata(query, max_results=max_videos)
            if videos:
                self.context_logger.logger.info("Agent found YouTube videos", count=len(videos), query=query)

                # Guardar videos en Supabase
                for video in videos:
                    video_data = {
                        "youtube_id": video.get('video_id'),
                        "title": video.get('title'),
                        "description": video.get('description'),
                        "thumbnail_url": video.get('thumbnail_url'),
                        "channel_title": video.get('channel_title'),
                        "published_at": video.get('published_at'),
                        "duration": video.get('duration'),
                        "view_count": video.get('view_count'),
                        "embed_url": video.get('embed_url'),
                        "query_used": query
                    }
                    await db_service.save_video(video_data)
            else:
                self.context_logger.logger.warning("Agent found no YouTube videos", query=query)
            return videos
        except Exception as e:
            self.context_logger.logger.error("Error finding trending YouTube videos", query=query, error=str(e), exc_info=True)
            raise # Re-raise for Celery retry
        finally:
            await self.scraper.close() # Close after use in this context

    @scraper_context_logger.log_execution
    async def find_popular_news_articles(self, search_terms: List[str], news_sources: List[str], max_articles_per_source: int = 2) -> List[Dict[str, Any]]:
        """
        Finds popular news articles from specified sources based on search terms.
        Implements retry logic and extracts clean title, content, author, date.
        """
        # Scraper initialization/closing is handled by the Celery task wrapper
        all_articles: List[Dict[str, Any]] = []
        self.context_logger.logger.info("Agent searching for popular news articles", search_terms=search_terms, news_sources=news_sources)

        for source_url in news_sources:
            self.context_logger.logger.info("Searching news from source", source_url=source_url)

            # Use a temporary scraper instance for each source to ensure fresh context/fingerprint
            temp_scraper = StealthScraper()
            try:
                await temp_scraper.initialize()
                if not temp_scraper._is_initialized:
                    self.context_logger.logger.error("Failed to initialize temporary scraper", source_url=source_url, skipping=True)
                    continue

                context, page = await temp_scraper._create_stealth_context_and_page()
                if not await temp_scraper._human_like_navigation(page, source_url):
                    self.context_logger.logger.warning("Could not navigate to news source", source_url=source_url)
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
                        break

                    if any(term.lower() in link.lower() for term in search_terms):
                        self.context_logger.logger.info("Scraping article from link", link=link)
                        # The main scraper instance is used here for article content
                        # It will be initialized/closed by the Celery task wrapper
                        await self.scraper.initialize() # Ensure main scraper is initialized
                        article_data = await self.scraper.scrape_news_article(link)
                        await self.scraper.close() # Close main scraper after use

                        if article_data:
                            if any(term.lower() in article_data.get('title', '').lower() for term in search_terms) or \
                               any(term.lower() in article_data.get('content', '').lower() for term in search_terms):
                                all_articles.append(article_data)
                                articles_from_source += 1
                                self.context_logger.logger.info("Successfully scraped and matched article", title=article_data.get('title'))
                            else:
                                self.context_logger.logger.debug("Article did not match search terms in title/content", link=link)
                        else:
                            self.context_logger.logger.debug("Failed to scrape article", link=link)
                    else:
                        self.context_logger.logger.debug("Skipping link as it does not match search terms in URL", link=link)

            except Exception as e:
                self.context_logger.logger.error("Error processing news source", source_url=source_url, error=str(e), exc_info=True)
                raise # Re-raise for Celery retry
            finally:
                await temp_scraper.close()

        self.context_logger.logger.info("Agent found news articles in total", count=len(all_articles))
        return all_articles

# Removed example usage and venv check as orchestration will handle execution
