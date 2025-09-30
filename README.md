# Hive Content Generation System

This project implements an autonomous content generation system ("Hive") that scrapes trending content, writes humanized articles, and simulates publishing them. It uses Playwright for stealthy web scraping, various AI services for content generation, and Celery with Redis for task orchestration.

## Features

*   **Stealthy Web Scraping:** Uses Playwright with `playwright-stealth` for anti-detection, user-agent rotation, random delays, and human-like navigation.
*   **YouTube Metadata Scraping:** Extracts metadata (title, description, thumbnail, embed URL) from YouTube videos based on keywords (no video downloads).
*   **News Article Scraping:** Scrapes popular news articles from specified sources, extracting clean content, title, author, and date.
*   **Humanized Article Writing:** Generates unique, human-like articles using multiple AI providers (Groq, Cohere, HuggingFace, Gemini) with prompt variation and robotic content detection.
*   **Celery & Redis Orchestration:** Manages the end-to-end workflow (Scrape → Write → Publish) using asynchronous tasks, queues, and automatic retries.
*   **Autonomous Workflow:** Configured with Celery Beat to run the content generation pipeline periodically (e.g., hourly).
*   **Modular Agent Design:** Separates concerns into `ScraperAgent`, `WriterAgent`, and `PublisherAgent`.
*   **Graceful Shutdown:** The main application handles system signals for a clean shutdown.
*   **Health Checks:** `HiveManager` provides basic health checks for Redis and Celery components.

## System Architecture

The system consists of the following main components:

*   **`main.py`**: The primary entry point for the application.
*   **`core/celery_config.py`**: Celery application configuration, including Redis broker/backend, queues, and Beat schedule.
*   **`core/hive_manager.py`**: Manages the overall system lifecycle, health checks, and graceful shutdown.
*   **`services/scraper_service.py`**: Implements the core stealth web scraping logic using Playwright.
*   **`services/ai_providers.py`**: Manages connections and API key rotation for various AI text generation services.
*   **`agents/content_scraper.py`**: An agent that uses `StealthScraper` to find trending YouTube videos and news articles.
*   **`agents/content_writer.py`**: An agent that uses `AI_Providers` to generate humanized articles from scraped content.
*   **`agents/content_publisher.py`**: A basic agent that simulates publishing generated content.
*   **`tasks/orchestrator.py`**: Defines the Celery tasks that wrap the agent functionalities and chains them into a complete content generation pipeline.

## Setup and Installation

### 1. Clone the Repository

```bash
git clone [repository_url]
cd motor\ v2.0 # Adjust if your directory name is different
```

### 2. Create and Activate a Virtual Environment

It's highly recommended to use a virtual environment.

**Windows:**
```bash
python -m venv venv
.\venv\Scripts\activate
```

**macOS/Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Install Playwright Browsers

Playwright requires browser binaries.
```bash
playwright install
```

### 5. Install Redis

This project uses Redis as the message broker and result backend for Celery.
*   **Windows:** Download and install from [Redis for Windows](https://github.com/microsoftarchive/redis/releases).
*   **macOS:** `brew install redis`
*   **Linux:** `sudo apt-get install redis-server` or equivalent package manager command.

Ensure your Redis server is running before starting the Hive system.

### 6. Configure Environment Variables

Create a `.env` file in the root directory of the project. This file will store your API keys and other configurations.

```dotenv
# Redis Configuration
REDIS_URL=redis://localhost:6379/0

# AI Service API Keys (at least one is required for content generation)
# You can provide multiple keys for rotation (e.g., GROQ_API_KEY_1, GROQ_API_KEY_2)
GROQ_API_KEY_1=your_groq_api_key_here
# GROQ_API_KEY_2=your_second_groq_api_key_here

COHERE_API_KEY_1=your_cohere_api_key_here
# COHERE_API_KEY_2=your_second_cohere_api_key_here

HUGGINGFACE_API_KEY_1=your_huggingface_api_key_here
# HUGGINGFACE_API_KEY_2=your_second_huggingface_api_key_here

GEMINI_API_KEY_1=your_gemini_api_key_here
# GEMINI_API_KEY_2=your_second_gemini_api_key_here
```
Replace `your_..._api_key_here` with your actual API keys.

## Running the System

The Hive system runs as several independent processes: the Redis server, a Celery worker, a Celery Beat scheduler, and the main application.

### 1. Start Redis Server

Ensure your Redis server is running in the background.
*   **Windows:** Start the Redis service or run `redis-server.exe` from its installation directory.
*   **macOS/Linux:** `redis-server`

### 2. Start Celery Worker

Open a **new terminal** in the project root and run the Celery worker. This worker will process the tasks.
```bash
celery -A core.celery_config worker -l info -P eventlet -Q scraper_queue,writer_queue,publisher_queue,default
```
*   **Note:** `-P eventlet` is crucial for handling asynchronous tasks (like Playwright scraping). If you don't have `eventlet` installed, run `pip install eventlet`.

### 3. Start Celery Beat Scheduler

Open a **third terminal** in the project root and run the Celery Beat scheduler. This will periodically enqueue the `start_scraping_pipeline` task.
```bash
celery -A core.celery_config beat -l info
```

### 4. Start the Main Application (Optional, for health monitoring)

Open a **fourth terminal** in the project root and run the main application. This will perform initial health checks and keep the system running, monitoring for shutdown signals.
```bash
python main.py
```
*   You can stop this process gracefully by pressing `Ctrl+C`.

## Testing the Full Pipeline Manually

To manually trigger a full content generation pipeline run (Scrape → Write → Publish) without waiting for Celery Beat's schedule:

1.  Ensure Redis, Celery Worker, and Celery Beat are running as described above.
2.  Open a **new terminal** and run:
    ```bash
    python main.py --test-pipeline
    ```
    This will enqueue the `start_scraping_pipeline` task immediately. Monitor the Celery worker logs to see the tasks being processed.

## Troubleshooting

*   **"Playwright or playwright-stealth not installed" / "youtube-search-python not installed"**: Ensure `pip install -r requirements.txt` was successful and your virtual environment is active.
*   **"No AI services are available"**: Check your `.env` file. Ensure you have at least one `*_API_KEY_1` set for an AI service and that the corresponding library is installed.
*   **"Redis connection error"**: Ensure your Redis server is running and `REDIS_URL` in your `.env` file is correct.
*   **"Celery command not found"**: Ensure Celery is installed (`pip install celery`) and your virtual environment is active.
*   **Celery tasks not running**:
    *   Verify the Celery worker is running in a separate terminal.
    *   Check the worker's logs for errors.
    *   Ensure the `-P eventlet` flag is used for the worker if you have async tasks.
*   **Celery Beat not scheduling tasks**:
    *   Verify Celery Beat is running in a separate terminal.
    *   Check Beat's logs for scheduling messages.
    *   Ensure the `beat_schedule` in `core/celery_config.py` is correctly configured.
*   **Content seems robotic or too short**: The `HumanizedWriter` has internal retry mechanisms. If issues persist, review the AI service API keys and consider adjusting `max_tokens` or `temperature` in `services/ai_providers.py` or `agents/content_writer.py`.
*   **Scraping is blocked**: Websites might update their anti-bot measures. You may need to update `services/scraper_service.py` with new user agents, more complex navigation patterns, or consider using proxy rotation (not implemented in this version).

## Future Enhancements

*   **Proxy Rotation:** Integrate a proxy rotation service for enhanced anti-detection.
*   **CAPTCHA Solving:** Integrate with a CAPTCHA solving service for automated handling of CAPTCHAs.
*   **Dynamic Trending Topic Discovery:** Implement an initial scraping phase to dynamically identify trending topics for YouTube and news, rather than relying on predefined queries.
*   **Database Integration:** Replace simulated publishing with actual database writes (e.g., Supabase, PostgreSQL).
*   **Monitoring Dashboard:** Integrate with tools like Flower (for Celery monitoring), Prometheus, and Grafana for comprehensive system monitoring.
*   **Advanced Content Filtering:** Implement more sophisticated NLP techniques for content relevance and quality filtering.
*   **`robots.txt` Compliance:** Add logic to parse and respect `robots.txt` rules for scraped domains.
