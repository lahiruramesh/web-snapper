"""
Web crawler module using the Crawl4AI API service.
Makes HTTP requests to a running Crawl4AI Docker container.
"""
import os
import json
import time
import datetime
import requests
import asyncio
from urllib.parse import urljoin, urlparse
import tempfile
import shutil
from bs4 import BeautifulSoup

from utils import (
    sanitize_filename, 
    is_valid_image_url, 
    download_image,
    extract_all_text,
    check_keyword_relevance
)

# Crawl4AI API settings
API_BASE_URL = "http://localhost:11235"
API_TOKEN = "your_secret_token"

class Crawl4AiClient:
    def __init__(self, base_url=API_BASE_URL, api_token=API_TOKEN):
        self.base_url = base_url
        self.headers = {"Authorization": f"Bearer {api_token}"} if api_token else {}
        
    def submit_crawl(self, urls, config=None):
        """Submit a crawl job to the API"""
        if isinstance(urls, str):
            urls = [urls]
            
        request_data = {
            "urls": urls,
            "params": {  # Changed from "crawler_params" to "params"
                "headless": True,
                "page_timeout": 60000
            }
        }
        
        # Add custom crawl configuration if provided
        if config:
            request_data.update(config)
        
        # Try the v1 API endpoint
        response = requests.post(
            f"{self.base_url}/crawl",  # Changed endpoint 
            headers=self.headers,
            json=request_data
        )
        response.raise_for_status()
        return response.json()["task_id"]

    def get_task_status(self, task_id):
        """Check the status of a crawl task"""
        response = requests.get(
            f"{self.base_url}/task/{task_id}",  # Changed endpoint
            headers=self.headers
        )
        response.raise_for_status()
        return response.json()

    
    def wait_for_completion(self, task_id, interval=2, timeout=300):
        """Wait for a task to complete"""
        start_time = time.time()
        while True:
            if time.time() - start_time > timeout:
                raise TimeoutError(f"Task {task_id} timed out after {timeout} seconds")
                
            status = self.get_task_status(task_id)
            
            if status["status"] == "completed":
                return status["result"]
            elif status["status"] == "failed":
                raise Exception(f"Task failed: {status.get('error', 'Unknown error')}")
            
            time.sleep(interval)

async def crawl_website(url, keywords=None, max_depth=2, max_pages=25, threshold=0.001, progress_callback=None):
    """
    Crawl a website using the Crawl4AI API service.
    
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
    if keywords is None:
        keywords = ["sustainability", "environment", "green", "eco"]
    
    # Create timestamp and directories for results
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    directory = f"crawler_results_{timestamp}"
    os.makedirs(directory, exist_ok=True)
    
    images_dir = os.path.join(directory, "images")
    os.makedirs(images_dir, exist_ok=True)
    
    debug_dir = os.path.join(directory, "debug")
    os.makedirs(debug_dir, exist_ok=True)
    
    # Initialize counters
    pages_crawled = 0
    matched_pages = 0
    total_matched_images = 0
    
    client = Crawl4AiClient()
    
    # Prepare crawl configuration
    crawl_config = {
        "deep_crawl": True,
        "max_depth": max_depth,
        "max_pages": max_pages,
        "crawler_params": {
            "headless": True,
        },
        "extra": {
            "delay_before_return_html": 1.0
        }
    }
    
    # For progress callback
    if progress_callback:
        progress_callback(0, max_pages, 0, 0, "Submitting crawl job...")
    
    # Submit crawl job
    try:
        task_id = client.submit_crawl(url, crawl_config)
        
        if progress_callback:
            progress_callback(0, max_pages, 0, 0, f"Crawling in progress (Task ID: {task_id})...")
        
        # Wait for results with progress updates
        start_time = time.time()
        crawl_results = []
        
        # Poll for results
        while True:
            # Allow for asyncio cooperative multitasking
            await asyncio.sleep(0.1)
            
            try:
                status = client.get_task_status(task_id)
                if status["status"] == "completed":
                    crawl_results = status["results"]
                    break
                elif status["status"] == "failed":
                    raise Exception(f"Crawl task failed: {status.get('error', 'Unknown error')}")
                
                # Estimate progress
                elapsed = time.time() - start_time
                if progress_callback and elapsed > 2:  # Update progress every 2 seconds
                    progress_callback(min(int(elapsed/3), max_pages-1), max_pages, matched_pages, total_matched_images, "Crawling...")
                    
                await asyncio.sleep(2)
                
            except Exception as e:
                print(f"Error checking task status: {str(e)}")
                await asyncio.sleep(5)
        
        # Process results
        processed_results = []
        summary_filename = os.path.join(directory, "summary.txt")
        
        with open(summary_filename, 'w', encoding='utf-8') as f:
            f.write(f"Web Crawler Results - {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Base URL: {url}\n")
            f.write(f"Crawled {len(crawl_results)} pages in total\n")
            f.write(f"Keywords: {', '.join(keywords)}\n\n")
            
            for i, result in enumerate(crawl_results, 1):
                pages_crawled = i
                
                if progress_callback:
                    progress_callback(pages_crawled, len(crawl_results), matched_pages, total_matched_images, "Processing results...")
                
                # Process HTML content
                html_content = result.get('cleaned_html', '')
                page_url = result.get('url', '')
                page_text = ""
                
                if not html_content:
                    print(f"Warning: No HTML content found for {page_url}. Result keys: {result.keys()}")
                    # Try to find HTML content in other possible fields
                    for key in ['content', 'body', 'page_content', 'raw_html']:
                        if key in result and result[key]:
                            html_content = result[key]
                            print(f"Found HTML content in alternative field: {key}")
                            break
                
                # Save raw HTML for debugging
                debug_html_file = os.path.join(debug_dir, f"{i:03d}_raw.html")
                with open(debug_html_file, 'w', encoding='utf-8') as debug_file:
                    debug_file.write(html_content)
                
                try:
                    # Extract only the main content without headers/footers
                    soup = BeautifulSoup(html_content, 'html.parser')
                    
                    # First, remove all script and style elements
                    for script in soup(["script", "style", "noscript"]):
                        script.extract()
                    
                    # Remove common header/footer/navigation elements
                    for element in soup.select('header, footer, nav, .header, .footer, .navigation, .nav, .menu, .sidebar, #header, #footer, #nav, #menu, #sidebar, [class*="header"], [class*="footer"], [class*="nav"], [id*="header"], [id*="footer"], [id*="nav"]'):
                        element.extract()
                        
                    # Also try to find content by common content containers
                    main_content = None
                    for content_container in ['main', 'article', '.content', '#content', '.main-content', '#main-content', '.post', '.article', 'section', 'p']:
                        content_elements = soup.select(content_container)
                        if content_elements:
                            main_content = content_elements[0]
                            break
                    
                    # Extract text from main content if found, otherwise from the filtered page
                    if main_content:
                        page_text = main_content.get_text(separator='\n', strip=True)
                    else:
                        page_text = soup.get_text(separator='\n', strip=True)
                    
                    # If we still don't have text content, check if the API directly provides it
                    if not page_text.strip() and result.get('text'):
                        page_text = result.get('text')
                    
                except Exception as e:
                    print(f"Error extracting text from {page_url}: {str(e)}")
                    page_text = "Error extracting text content"
                
                debug_text_file = os.path.join(debug_dir, f"{i:03d}_text.txt")
                with open(debug_text_file, 'w', encoding='utf-8') as debug_file:
                    debug_file.write(page_text)
                
                # Check keyword relevance
                is_relevant, match_count, keyword_matches = check_keyword_relevance(page_text, keywords, threshold)
                
                # Create filenames for saving results
                page_filename = f"{i:03d}_{sanitize_filename(page_url)}.txt"
                page_filepath = os.path.join(directory, page_filename)
                
                # Process images
                page_images = []
                soup = BeautifulSoup(html_content, 'html.parser')
                img_tags = soup.find_all('img')
                
                for img in img_tags:
                    img_url = img.get('src')
                    alt_text = img.get('alt', '')
                    
                    img_is_relevant = any(keyword.lower() in alt_text.lower() for keyword in keywords) if alt_text else False
                    
                    if is_valid_image_url(img_url) and (img_is_relevant or is_relevant):
                        img_name, img_path = download_image(img_url, page_url, images_dir)
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
                        progress_callback(pages_crawled, len(crawl_results), matched_pages, total_matched_images, "Processing...")
                
                # Prepare result data
                page_result = {
                    'url': page_url,
                    'depth': result.get('depth', 0),
                    'title': result.get('title', 'N/A'),
                    'status_code': result.get('status_code', 'Unknown'),
                    'text': page_text,
                    'text_file': page_filepath,
                    'images': page_images,
                    'keyword_matches': match_count,
                    'keyword_details': keyword_matches,
                    'relevance_score': match_count / len(page_text.split()) if page_text else 0,
                    'is_relevant': is_relevant
                }
                
                processed_results.append(page_result)
                
                # Save content to files
                _write_page_content_file(page_filepath, result, page_text, is_relevant, 
                                        match_count, keyword_matches, page_images)
                
                _write_summary_entry(f, i, result, is_relevant, match_count, 
                                    keyword_matches, page_images, page_filename)
            
            # Note: This should be outside the for loop
            _write_summary_statistics(f, crawl_results, matched_pages, total_matched_images)
            
        return {
            'directory': directory,
            'summary_file': summary_filename,
            'results': processed_results,
            'images_dir': images_dir,
            'total_pages': len(crawl_results),
            'matched_pages': matched_pages,
            'matched_images': total_matched_images
        }
        
    except Exception as e:
        print(f"Error during API crawling: {str(e)}")
        raise

# Helper functions for writing results
def _write_page_content_file(filepath, result, page_text, is_relevant, match_count, 
                           keyword_matches, page_images):
    """Helper function to write page content to file"""
    with open(filepath, 'w', encoding='utf-8') as page_file:
        page_file.write(f"URL: {result.get('url', 'N/A')}\n")
        page_file.write(f"Title: {result.get('title', 'N/A')}\n")
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
    f.write(f"URL: {result.get('url', 'N/A')}\n")
    f.write(f"Title: {result.get('title', 'N/A')}\n")
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