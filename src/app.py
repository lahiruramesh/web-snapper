"""
Web Crawler Application Entry Point
Handles browser lifecycle management for Docker environment
"""
import os
import streamlit as st
import asyncio
from contextlib import asynccontextmanager
from playwright.async_api import async_playwright
import streamlitapp as main

# Configure environment variables for Playwright in Docker
os.environ["PLAYWRIGHT_BROWSERS_PATH"] = "/ms-playwright"
os.environ["PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD"] = "1"

# Global browser instance with proper context management
browser_instance = None
playwright_instance = None

@asynccontextmanager
async def get_browser():
    """Get a persistent browser instance with proper lifecycle management"""
    global browser_instance, playwright_instance
    
    if browser_instance is None:
        try:
            # Start playwright if needed
            if playwright_instance is None:
                playwright_instance = await async_playwright().start()
            
            # Launch the browser with Docker-compatible options
            browser_instance = await playwright_instance.chromium.launch(
                headless=True,
                args=[
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-gpu',
                    '--single-process'
                ]
            )
            st.session_state.browser_ready = True
            print("✅ Browser launched successfully")
        except Exception as e:
            print(f"❌ Browser launch failed: {e}")
            if playwright_instance:
                await playwright_instance.stop()
                playwright_instance = None
            st.session_state.browser_ready = False
            raise e
    
    try:
        yield browser_instance
    except Exception as e:
        print(f"⚠️ Error during browser usage: {e}")
        await cleanup_browser()
        raise e

async def cleanup_browser():
    """Clean up browser resources"""
    global browser_instance, playwright_instance
    
    print("🧹 Cleaning up browser resources...")
    
    if browser_instance:
        try:
            await browser_instance.close()
            print("✅ Browser closed successfully")
        except Exception as e:
            print(f"⚠️ Error closing browser: {e}")
        browser_instance = None
    
    if playwright_instance:
        try:
            await playwright_instance.stop()
            print("✅ Playwright stopped successfully")
        except Exception as e:
            print(f"⚠️ Error stopping playwright: {e}")
        playwright_instance = None
    
    st.session_state.browser_ready = False

# Update crawler.py's browser handling without modifying the file
from crawler import crawl_website as original_crawl_website

async def crawl_website_wrapper(*args, **kwargs):
    """Wrap the crawler to use our managed browser"""
    async with get_browser():
        try:
            return await original_crawl_website(*args, **kwargs)
        except Exception as e:
            print(f"❌ Crawl error: {e}")
            raise e

# Patch the crawler module to use our wrapper
import crawler
crawler.crawl_website = crawl_website_wrapper

# Initialize session state
if 'browser_ready' not in st.session_state:
    st.session_state.browser_ready = False
    
# Main app entry point
if __name__ == "__main__":
    # Show diagnostics info at startup
    print(f"🔍 Playwright browsers path: {os.environ.get('PLAYWRIGHT_BROWSERS_PATH', 'not set')}")
    print(f"🔧 Running in Docker environment")
    
    try:
        # Run the main application with our patched crawler
        main.main()
    except KeyboardInterrupt:
        print("👋 Application terminated by user")
        asyncio.run(cleanup_browser())
    except Exception as e:
        print(f"❌ Application error: {e}")
        asyncio.run(cleanup_browser())
        raise e