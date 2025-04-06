import os
import requests
from typing import Dict, Any
import asyncio
from dotenv import load_dotenv

CRAWL4AI_API_URL = os.getenv("CRAWL4AI_API_URL", "http://localhost:11235")
API_TOKEN = os.getenv("CRAWL4AI_API_TOKEN")

async def crawl_website(
    url: str,
    keywords: list,
    max_depth: int = 2,
    max_pages: int = 10,
    progress_callback: callable = None
) -> Dict[str, Any]:
    """Crawl website using Crawl4AI API"""
    headers = {"Authorization": f"Bearer {API_TOKEN}"} if API_TOKEN else {}
    
    payload = {
        "urls": [url],
        "extraction_config": {
            "mode": "cosine",
            "params": {
                "semantic_filter": " ".join(keywords),
                "word_count_threshold": 50,
                "max_dist": 0.25
            }
        },
        "crawl_config": {
            "max_depth": max_depth,
            "max_pages": max_pages
        }
    }

    try:
        # Start crawl job
        response = requests.post(
            f"{CRAWL4AI_API_URL}/crawl",
            headers=headers,
            json=payload,
            timeout=30
        )
        response.raise_for_status()
        
        task_id = response.json()['task_id']
        return await poll_crawl_status(task_id, progress_callback)
        
    except Exception as e:
        return handle_crawl_error(e)

async def poll_crawl_status(task_id: str, progress_callback: callable) -> Dict[str, Any]:
    """Poll Crawl4AI API for crawl completion"""
    status_url = f"{CRAWL4AI_API_URL}/tasks/{task_id}"
    
    while True:
        response = requests.get(status_url)
        status = response.json()
        
        if status['state'] == 'COMPLETED':
            return format_crawl_results(status['result'])
            
        if progress_callback:
            progress_callback(
                current_page=status.get('pages_crawled', 0),
                total_pages=status.get('total_pages', 0),
                matched_pages=status.get('relevant_pages', 0),
                matched_images=status.get('images_extracted', 0)
            )
            
        await asyncio.sleep(2)

def format_crawl_results(api_data: Dict) -> Dict[str, Any]:
    """Convert Crawl4AI API response to web-snapper format"""
    return {
        'total_pages': api_data.get('total_pages', 0),
        'matched_pages': api_data.get('relevant_pages', 0),
        'matched_images': api_data.get('images_extracted', 0),
        'results': [{
            'url': page['url'],
            'title': page.get('metadata', {}).get('title', 'No title'),
            'text': page.get('extracted_text', ''),
            'images': [img['url'] for img in page.get('images', [])],
            'depth': page.get('depth', 0),
            'relevance_score': page.get('relevance_score', 0),
            'keyword_matches': list(page.get('matched_keywords', {}).keys())
        } for page in api_data.get('pages', [])]
    }
