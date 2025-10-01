import asyncio
import random
import time
from typing import Dict, List, Optional, Any, Tuple
from urllib.parse import urlparse
import sys

# Import the global db_service instance
from database.database_service import db_service

# Import logging from core.logging_config
from core.logging_config import get_logger, log_execution
logger = get_logger('scraper')

# Import circuit breaker
from core.circuit_breaker import with_circuit_breaker, CircuitBreakerOpenException

# Optional imports for graceful fallback
_PLAYWRIGHT_AVAILABLE = False
try:
    from playwright.async_api import async_playwright, Page, BrowserContext, Browser
    import playwright_stealth
    _PLAYWRIGHT_AVAILABLE = True
except ImportError as e:
    logger.debug(f"Playwright not available: {e}. StealthScraper will be unavailable.")

_YOUTUBE_SEARCH_AVAILABLE = False
try:
    from youtubesearchpython import VideosSearch
    _YOUTUBE_SEARCH_AVAILABLE = True
except ImportError:
    logger.warning("youtube-search-python not installed. YouTube scraping via API will be limited. Please install with 'pip install youtube-search-python'")

class StealthScraper:
    """
    A stealthy web scraper using Playwright with anti-detection techniques.
    Handles user-agent rotation, random delays, and automatic retries.
    """
    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/120.0.0.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Safari/605.1.15",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/120.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:109.0) Gecko/20100101 Firefox/120.0",
        "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
    ]

    def __init__(self):
        self._playwright_instance = None
        self._browser: Optional[Browser] = None
        self._is_initialized = False
        if not _PLAYWRIGHT_AVAILABLE:
            logger.error("StealthScraper cannot be initialized: Playwright or playwright-stealth is not installed.")
            return
        logger.info("StealthScraper initialized. Call .initialize() before use.")

    @log_execution(logger_name='scraper')
    async def initialize(self):
        """Initializes the Playwright instance and a shared browser."""
        if self._is_initialized:
            return
        try:
            self._playwright_instance = await async_playwright().start()
            self._browser = await self._playwright_instance.chromium.launch(headless=True)
            self._is_initialized = True
            logger.info("Playwright instance and shared browser initialized.")
        except Exception as e:
            logger.error(f"Failed to initialize Playwright: {e}")
            self._is_initialized = False
            raise

    @log_execution(logger_name='scraper')
    async def close(self):
        """Closes the Playwright browser and instance."""
        if self._browser:
            await self._browser.close()
            self._browser = None
        if self._playwright_instance:
            await self._playwright_instance.stop()
            self._playwright_instance = None
        self._is_initialized = False
        logger.info("Playwright browser and instance closed.")

    @log_execution(logger_name='scraper')
    async def _create_stealth_context_and_page(self) -> tuple[BrowserContext, Page]:
        """Creates a new browser context with stealth and a new page."""
        if not self._is_initialized or not self._browser:
            await self.initialize()
            if not self._is_initialized:
                raise RuntimeError("Scraper not initialized and failed to initialize.")

        context = await self._browser.new_context(
            user_agent=random.choice(self.USER_AGENTS),
            viewport={"width": 1920, "height": 1080},
            java_script_enabled=True,
            accept_downloads=False,
            locale="en-US,en;q=0.9", # Add locale for fingerprinting evasion
            timezone_id="America/New_York", # Add timezone for fingerprinting evasion
            device_scale_factor=1,
        )
        await playwright_stealth.stealth(context) # Apply stealth techniques
        page = await context.new_page()
        return context, page

    @log_execution(logger_name='scraper')
    async def _human_like_navigation(self, page: Page, url: str, timeout: int = 45000) -> bool:
        """Navigates to a URL with human-like behavior and random timeouts."""
        try:
            logger.info(f"Navigating to {url} with human-like behavior...")
            await page.goto(url, timeout=timeout, wait_until="domcontentloaded")
            await asyncio.sleep(random.uniform(1, 3)) # Initial random delay (1-3 seconds)

            # Simulate random scrolls
            scroll_count = random.randint(1, 5)
            for _ in range(scroll_count):
                await page.evaluate("window.scrollBy(0, window.innerHeight * (0.5 + Math.random()));")
                await asyncio.sleep(random.uniform(0.8, 2.5))

            # Simulate slight mouse movements (hard to make truly generic and effective without specific targets)
            # For now, focus on scrolls and delays.

            await asyncio.sleep(random.uniform(1, 3)) # Final random delay (1-3 seconds)
            return True
        except Exception as e:
            logger.error(f"Navigation to {url} failed: {e}")
            return False

    @log_execution(logger_name='scraper')
    async def _retry_operation(self, func, *args, max_retries: int = 3, **kwargs):
        """Implements an automatic retry system with exponential backoff."""
        for attempt in range(1, max_retries + 1):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                logger.warning(f"Attempt {attempt}/{max_retries} failed: {e}")
                if attempt < max_retries:
                    await asyncio.sleep(2 ** attempt + random.uniform(0, 2)) # Exponential backoff with jitter
                else:
                    logger.error(f"Max retries reached for operation. Last error: {e}")
                    raise

    @with_circuit_breaker(name="youtube_scraper", expected_exception=CircuitBreakerOpenException)
    @log_execution(logger_name='scraper')
    async def scrape_youtube_metadata(self, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        """
        Scrapes YouTube video metadata using youtube-search-python (if available)
        or a basic Playwright search. Does NOT download videos.
        """
        if not _PLAYWRIGHT_AVAILABLE:
            logger.error("Playwright is not available. Cannot scrape YouTube metadata.")
            return []

        results = []
        if _YOUTUBE_SEARCH_AVAILABLE:
            logger.info(f"Searching YouTube for '{query}' using youtubesearchpython...")
            try:
                videos_search = VideosSearch(query, limit=max_results)
                search_results = await asyncio.to_thread(videos_search.result)
                for video in search_results.get('result', []):
                    results.append({ # Corrected indentation
                        "title": video.get('title'),
                        "id": video.get('id'),
                        "url": video.get('link'),
                        "embed_url": f"https://www.youtube.com/embed/{video.get('id')}" if video.get('id') else None,
                        "duration": video.get('duration'),
                        "views": video.get('viewCount', {}).get('text'),
                        "channel": video.get('channel', {}).get('name'),
                        "thumbnail": video.get('thumbnails', [None])[-1].get('url') if video.get('thumbnails') else None,
                        "description": None # youtubesearchpython doesn't provide full description directly in search results
                    })
                # Save video metadata to Supabase
                if db_service.is_connected():
                    for video_data in results:
                        await db_service.save_video(video_data)
                else:
                    logger.warning("Supabase not connected. Skipping saving video metadata.")

                logger.info(f"Found {len(results)} videos via youtubesearchpython.")
                return results
            except Exception as e: # This except block now correctly belongs to the youtubesearchpython try block
                logger.warning(f"youtubesearchpython failed: {e}. Falling back to Playwright search.")

        # Fallback to Playwright if youtube-search-python fails or is not available
        logger.info(f"Searching YouTube for '{query}' using Playwright...")
        context: Optional[BrowserContext] = None
        page: Optional[Page] = None
        try: # This is a separate, correctly indented try block for Playwright search
            context, page = await self._retry_operation(self._create_stealth_context_and_page)
            if not await self._human_like_navigation(page, f"https://www.youtube.com/results?search_query={query}"):
                return []

            # Wait for search results to load
            await page.wait_for_selector("ytd-video-renderer", timeout=15000)
            await asyncio.sleep(random.uniform(2, 5)) # Additional delay after loading

            video_elements = await page.query_selector_all("ytd-video-renderer")
            for i, element in enumerate(video_elements[:max_results]):
                title_element = await element.query_selector("#video-title")
                url_element = await element.query_selector("a#video-title")
                channel_element = await element.query_selector("yt-formatted-string.ytd-channel-name")
                views_element = await element.query_selector("span.ytd-video-meta-block:nth-child(1)")
                duration_element = await element.query_selector("span.ytd-thumbnail-overlay-time-status-renderer")

                title = await title_element.text_content() if title_element else "N/A"
                url = await url_element.get_attribute("href") if url_element else "N/A"
                channel = await channel_element.text_content() if channel_element else "N/A"
                views = await views_element.text_content() if views_element else "N/A"
                duration = await duration_element.text_content().strip() if duration_element else "N/A"

                video_id = urlparse(url).query.split('v=')[-1].split('&')[0] if 'v=' in url else None

                video_data = {
                    "title": title,
                    "id": video_id,
                    "url": f"https://www.youtube.com{url}" if url and not url.startswith("http") else url,
                    "embed_url": f"https://www.youtube.com/embed/{video_id}" if video_id else None,
                    "duration": duration,
                    "views": views,
                    "channel": channel,
                    "thumbnail": f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg" if video_id else None,
                    "description": None # Playwright search results don't easily expose full description
                }
                results.append(video_data)

                # Save video metadata to Supabase
                if db_service.is_connected():
                    await db_service.save_video(video_data)
                else:
                    logger.warning("Supabase not connected. Skipping saving video metadata.")

            logger.info(f"Found {len(results)} videos via Playwright search.")
            return results
        except Exception as e:
            logger.error(f"Failed to scrape YouTube metadata with Playwright: {e}")
            return []
        finally:
            if page:
                await page.close()
            if context:
                await context.close()

    @with_circuit_breaker(name="news_scraper", expected_exception=CircuitBreakerOpenException)
    @log_execution(logger_name='scraper')
    async def scrape_news_article(self, url: str) -> Optional[Dict[str, Any]]:
        """
        Scrapes a news article from a given URL, extracting title, content, author, and date.
        Uses Playwright with anti-detection.
        """
        if not _PLAYWRIGHT_AVAILABLE:
            logger.error("Playwright is not available. Cannot scrape news articles.")
            return None

        context: Optional[BrowserContext] = None
        page: Optional[Page] = None
        try:
            context, page = await self._retry_operation(self._create_stealth_context_and_page)
            if not await self._human_like_navigation(page, url):
                return None

            # Attempt to extract common elements
            title = await page.title()

            # Enhanced heuristic for content extraction
            # Prioritize common article content containers
            content_selectors = [
                "article",
                "div[itemprop='articleBody']",
                "div.article-content",
                "div.entry-content",
                "div.post-content",
                "main",
                "body" # Fallback
            ]

            full_content = ""
            for selector in content_selectors:
                content_container = await page.query_selector(selector)
                if content_container:
                    # Extract text from paragraphs within the container
                    content_parts = await content_container.query_selector_all("p")
                    full_content = "\n".join([await p.text_content() for p in content_parts if await p.text_content()])
                    if full_content:
                        break

            if not full_content: # If paragraphs didn't yield content, try direct text from container
                if content_container:
                    full_content = await content_container.text_content()
                    # Basic cleaning to remove excessive whitespace/newlines
                    full_content = ' '.join(full_content.split()).strip()


            # Heuristic for author and date (highly site-dependent)
            author = await page.evaluate("""
                () => {
                    const selectors = [
                        'meta[name="author"]',
                        'meta[property="article:author"]',
                        'meta[itemprop="author"]',
                        '[itemprop="author"]',
                        '.author',
                        '.byline',
                        '.post-author'
                    ];
                    for (const selector of selectors) {
                        const el = document.querySelector(selector);
                        if (el) return el.content || el.textContent.trim();
                    }
                    return null;
                }
            """)
            date = await page.evaluate("""
                () => {
                    const selectors = [
                        'meta[property="article:published_time"]',
                        'meta[name="date"]',
                        'meta[itemprop="datePublished"]',
                        'time[datetime]',
                        '.date',
                        '.timestamp',
                        '.post-date'
                    ];
                    for (const selector of selectors) {
                        const el = document.querySelector(selector);
                        if (el) return el.content || el.datetime || el.textContent.trim();
                    }
                    return null;
                }
            """)

            article_data = {
                "title": title,
                "url": url,
                "content": full_content,
                "author": author,
                "date": date,
            }

            # Save article data to Supabase
            if db_service.is_connected():
                await db_service.save_article(article_data)
            else:
                logger.warning("Supabase not connected. Skipping saving article data.")

            logger.info(f"Successfully scraped article from {url}. Title: {title[:50]}...")
            return article_data
        except Exception as e:
            logger.error(f"Failed to scrape news article from {url}: {e}")
            return None
        finally:
            if page:
                await page.close()
            if context:
                await context.close()

# Example usage (for testing purposes)
async def main():
    scraper = StealthScraper()
    await scraper.initialize()

    if scraper._is_initialized:
        print("\n--- YouTube Metadata ---")
        youtube_videos = await scraper.scrape_youtube_metadata("AI trends 2025", max_results=3)
        for video in youtube_videos:
            print(f"Title: {video.get('title')}\nURL: {video.get('url')}\nEmbed URL: {video.get('embed_url')}\nChannel: {video.get('channel')}\n")

        print("\n--- News Article ---")
        article_url = "https://www.bbc.com/news/technology-62009900" # Example URL, might need to be updated
        news_article = await scraper.scrape_news_article(article_url)
        if news_article:
            print(f"Title: {news_article.get('title')}")
            print(f"Author: {news_article.get('author')}")
            print(f"Date: {news_article.get('date')}")
            print(f"Content (first 200 chars): {news_article.get('content', '')[:200]}...")
        else:
            print(f"Failed to scrape article from {article_url}")

    await scraper.close()

def check_venv_active():
    """Checks if the script is running inside a virtual environment."""
    if not hasattr(sys, 'base_prefix') or sys.base_prefix == sys.prefix:
        logger.error("It appears you are not running inside a virtual environment.")
        logger.error("Please activate your virtual environment before running this script.")
        logger.error("For Windows, use: .\\venv\\Scripts\\activate")
        logger.error("For macOS/Linux, use: source ./venv/bin/activate")
        sys.exit(1)
    logger.info("Virtual environment detected and active.")

if __name__ == "__main__":
    check_venv_active()
    asyncio.run(main())
