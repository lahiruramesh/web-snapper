def format_crawl4ai_response(api_data):
    """Convert Crawl4AI API response to web-snapper format"""
    return {
        'total_pages': api_data.get('stats', {}).get('total_pages', 0),
        'matched_pages': api_data.get('stats', {}).get('relevant_pages', 0),
        'results': [{
            'url': page['url'],
            'title': page.get('metadata', {}).get('title', 'No Title'),
            'text': page.get('extracted_text', ''),
            'images': [img['url'] for img in page.get('images', [])],
            'relevance': page.get('relevance_score', 0),
            'keywords': list(page.get('matched_keywords', {}).keys())
        } for page in api_data.get('pages', [])]
    }