"""
Web crawler module for extracting content and images from websites.
Uses crawl4ai library for crawling and BeautifulSoup for parsing.
"""
import asyncio
import os
import json
import re
import datetime
import subprocess
import platform
from bs4 import BeautifulSoup
from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, BrowserConfig
from crawl4ai.deep_crawling import BestFirstCrawlingStrategy
from crawl4ai.content_scraping_strategy import LXMLWebScrapingStrategy
from crawl4ai.deep_crawling.scorers import KeywordRelevanceScorer
import time


from utils import (
    sanitize_filename, 
    is_valid_image_url, 
    download_image,
    extract_all_text,
    check_keyword_relevance
)

def kill_chrome_processes():
    """Kill any lingering Chrome/Chromium processes that might be causing issues"""
    system = platform.system().lower()
    
    try:
        if system == 'darwin':  # macOS

            subprocess.run(['pkill', 'Chromium'], stderr=subprocess.DEVNULL)
        elif system == 'linux':
            subprocess.run(['pkill', 'chromium'], stderr=subprocess.DEVNULL)
        elif system == 'windows':
            subprocess.run(['taskkill', '/F', '/IM', 'chromium.exe'], stderr=subprocess.DEVNULL, shell=True)
        time.sleep(1)
        print("Cleaned up any existing browser processes")
    except Exception as e:
        print(f"Note: Process cleanup attempt: {str(e)}")

async def crawl_website(url, keywords=None, max_depth=2, max_pages=25, threshold=0.001, progress_callback=None):
    """
    Crawl a website and extract content including images.
    
    Args:
        url (str): The starting URL to crawl
        keywords (list): List of keywords to prioritize relevant content
        max_depth (int): Maximum crawl depth from starting URL
        max_pages (int): Maximum number of pages to crawl
        threshold (float): Relevance threshold for considering a page relevant
        progress_callback (function): Callback function for progress updates
        
    Returns:
        dict: Crawl results including directory paths and processed content
    """
    # Kill any lingering browser processes before starting
    kill_chrome_processes()
    
    if keywords is None:
        keywords = ["sustainability", "environment", "green", "eco"]
   
    scorer = KeywordRelevanceScorer(
        keywords=keywords,
        weight=0.7
    )
    
    strategy = BestFirstCrawlingStrategy(
        max_depth=max_depth,
        include_external=False,
        url_scorer=scorer,
        max_pages=max_pages,
    )
    
    config = CrawlerRunConfig(
        deep_crawl_strategy=strategy,
        scraping_strategy=LXMLWebScrapingStrategy(),
        verbose=True
    )

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    directory = f"crawler_results_{timestamp}"
    os.makedirs(directory, exist_ok=True)
    
    images_dir = os.path.join(directory, "images")
    os.makedirs(images_dir, exist_ok=True)
    
    debug_dir = os.path.join(directory, "debug")
    os.makedirs(debug_dir, exist_ok=True)
    
    pages_crawled = 0
    matched_pages = 0
    total_matched_images = 0
    
    # Enhanced browser config with explicit parameters
    browser_config = BrowserConfig(
        browser_type="chromium",
        headless=True,
    )

    crawler = None
    results = []
    
    try:
        # Create crawler with correct parameter name (browser_config)
        crawler = AsyncWebCrawler(config==browser_config)
        
        # Start the crawler
        await crawler.start()
        
        # Run the crawl
        results = await crawler.arun(url, config=config)
        
        processed_results = []
        matched_pages = 0
        total_matched_images = 0
        summary_filename = os.path.join(directory, "summary.txt")
        
        with open(summary_filename, 'w', encoding='utf-8') as f:
            f.write(f"Web Crawler Results - {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Base URL: {url}\n")
            f.write(f"Crawled {len(results)} pages in total\n")
            f.write(f"Keywords: {', '.join(keywords)}\n\n")
            
            for i, result in enumerate(results, 1):
                pages_crawled = i
                if progress_callback:
                    progress_callback(pages_crawled, len(results), matched_pages, total_matched_images)
                
                if hasattr(result, 'html') and result.html:
                    debug_html_file = os.path.join(debug_dir, f"{i:03d}_raw.html")
                    with open(debug_html_file, 'w', encoding='utf-8') as debug_file:
                        debug_file.write(result.html)
                    
                    page_text = extract_all_text(result.html, result.url)
                else:
                    page_text = result.text if hasattr(result, 'text') else ''
                
                debug_text_file = os.path.join(debug_dir, f"{i:03d}_text.txt")
                with open(debug_text_file, 'w', encoding='utf-8') as debug_file:
                    debug_file.write(page_text)
                
                is_relevant, match_count, keyword_matches = check_keyword_relevance(page_text, keywords, threshold)
                
                matched_pages += 1 if is_relevant else 0
                
                page_filename = f"{i:03d}_{sanitize_filename(result.url)}.txt"
                page_filepath = os.path.join(directory, page_filename)
                
                page_images = []
                if hasattr(result, 'html') and result.html:
                    soup = BeautifulSoup(result.html, 'html.parser')
                    img_tags = soup.find_all('img')
                    
                    for img in img_tags:
                        img_url = img.get('src')
                        alt_text = img.get('alt', '')
                        
                        img_is_relevant = any(keyword.lower() in alt_text.lower() for keyword in keywords) if alt_text else False
                        
                        if is_valid_image_url(img_url) and (img_is_relevant or is_relevant):
                            img_name, img_path = download_image(img_url, result.url, images_dir)
                            if img_name:
                                page_images.append({
                                    'filename': img_name,
                                    'path': img_path,
                                    'original_url': img_url,
                                    'alt_text': alt_text,
                                    'is_relevant': img_is_relevant
                                })
                
                if is_relevant:
                    matched_pages += 1
                    total_matched_images += len(page_images)
                    
                    if progress_callback:
                        progress_callback(pages_crawled, len(results), matched_pages, total_matched_images)
                
                page_result = {
                    'url': result.url,
                    'depth': result.metadata.get('depth', 0),
                    'title': result.title if hasattr(result, 'title') else 'N/A',
                    'status_code': result.status_code if hasattr(result, 'status_code') else 'Unknown',
                    'text': page_text,
                    'text_file': page_filepath,
                    'images': page_images,
                    'keyword_matches': match_count,
                    'keyword_details': keyword_matches,
                    'relevance_score': match_count / len(page_text.split()) if page_text else 0,
                    'is_relevant': is_relevant
                }
                
                processed_results.append(page_result)
                
                _write_page_content_file(page_filepath, result, page_text, is_relevant, 
                                        match_count, keyword_matches, page_images)
                
                _write_summary_entry(f, i, result, is_relevant, match_count, 
                                    keyword_matches, page_images, page_filename)
            
            _write_summary_statistics(f, results, matched_pages, total_matched_images)
            
    except Exception as e:
        print(f"Error during crawling: {str(e)}")
        raise
    
    finally:
        # Always ensure proper cleanup
        if crawler:
            try:
                await crawler.stop()
                print("Crawler stopped successfully")
            except Exception as e:
                print(f"Error stopping crawler: {e}")
                
        # Force kill any lingering processes to be extra safe
        kill_chrome_processes()
        
    return {
        'directory': directory,
        'summary_file': summary_filename,
        'results': processed_results,
        'images_dir': images_dir,
        'total_pages': len(results),
        'matched_pages': matched_pages,
        'matched_images': total_matched_images
    }

def _write_page_content_file(filepath, result, page_text, is_relevant, match_count, 
                           keyword_matches, page_images):
    """Helper function to write page content to file"""
    with open(filepath, 'w', encoding='utf-8') as page_file:
        page_file.write(f"URL: {result.url}\n")
        page_file.write(f"Title: {result.title if hasattr(result, 'title') else 'N/A'}\n")
        page_file.write(f"Relevant: {'Yes' if is_relevant else 'No'}\n")
        page_file.write(f"Keyword matches: {match_count}\n")
        page_file.write(f"Keyword details: {json.dumps(keyword_matches, indent=2)}\n\n")
        
        if page_images:
            page_file.write("=" * 50 + "\n")
            page_file.write("IMAGES\n")
            page_file.write("=" * 50 + "\n\n")
            for img in page_images:
                page_file.write(f"Image: {img['filename']}\n")
                page_file.write(f"URL: {img['original_url']}\n")
                if img['alt_text']:
                    page_file.write(f"Alt text: {img['alt_text']}\n")
                page_file.write("\n")
        
        page_file.write("=" * 50 + "\n")
        page_file.write("TEXT CONTENT\n")
        page_file.write("=" * 50 + "\n\n")
        
        if page_text:
            page_file.write(page_text[:10000] + "..." if len(page_text) > 10000 else page_text)
        else:
            page_file.write("No text content available")

def _write_summary_entry(f, index, result, is_relevant, match_count, 
                       keyword_matches, page_images, page_filename):
    """Helper function to write summary entry"""
    f.write(f"Result #{index}\n")
    f.write(f"URL: {result.url}\n")
    f.write(f"Title: {result.title if hasattr(result, 'title') else 'N/A'}\n")
    f.write(f"Relevant: {'Yes' if is_relevant else 'No'}\n")
    f.write(f"Keyword matches: {match_count}\n")
    f.write(f"Keyword details: {json.dumps(keyword_matches, indent=2)}\n")
    f.write(f"Images found: {len(page_images)}\n")
    f.write(f"Content saved to: {page_filename}\n")
    f.write("\n" + "-"*50 + "\n\n")

def _write_summary_statistics(f, results, matched_pages, total_matched_images):
    """Helper function to write summary statistics"""
    f.write("=" * 50 + "\n")
    f.write("SUMMARY STATISTICS\n")
    f.write("=" * 50 + "\n\n")
    f.write(f"Total pages crawled: {len(results)}\n")
    f.write(f"Pages with keyword matches: {matched_pages}\n")
    f.write(f"Total relevant images found: {total_matched_images}\n")