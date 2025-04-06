import os
import re
import requests
from urllib.parse import urlparse, urljoin
import uuid

def sanitize_filename(url):
    """Convert URL to a safe filename"""
    # Get the path part of the URL
    path = urlparse(url).path
    
    # Get the last part of the path (filename)
    filename = os.path.basename(path)
    
    # If filename is empty, use the netloc (domain)
    if not filename:
        filename = urlparse(url).netloc
    
    # Remove any special characters
    filename = re.sub(r'[^\w\-_.]', '_', filename)
    
    # Ensure filename is not too long
    if len(filename) > 50:
        filename = filename[:50]
    
    return filename

def is_valid_image_url(url):
    """Check if URL points to a valid image"""
    if not url:
        return False
    
    # Handle relative URLs
    if not url.startswith(('http://', 'https://')):
        return True  # We'll resolve relative URLs when downloading
    
    # Check if URL ends with common image extensions
    image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.svg']
    return any(url.lower().endswith(ext) for ext in image_extensions)

def download_image(img_url, base_url, save_dir):
    """Download an image and save it to disk"""
    try:
        # Handle relative URLs
        if not img_url.startswith(('http://', 'https://')):
            img_url = urljoin(base_url, img_url)
        
        # Get image content
        response = requests.get(img_url, timeout=10)
        if response.status_code != 200:
            return None, None
        
        # Detect content type and extension
        content_type = response.headers.get('Content-Type', '').lower()
        
        if 'image/jpeg' in content_type:
            ext = 'jpg'
        elif 'image/png' in content_type:
            ext = 'png'
        elif 'image/gif' in content_type:
            ext = 'gif'
        elif 'image/webp' in content_type:
            ext = 'webp'
        elif 'image/svg+xml' in content_type:
            ext = 'svg'
        else:
            # Try to determine extension from URL
            parsed_url = urlparse(img_url)
            path = parsed_url.path.lower()
            
            if path.endswith('.jpg') or path.endswith('.jpeg'):
                ext = 'jpg'
            elif path.endswith('.png'):
                ext = 'png'
            elif path.endswith('.gif'):
                ext = 'gif'
            elif path.endswith('.webp'):
                ext = 'webp'
            elif path.endswith('.svg'):
                ext = 'svg'
            else:
                # Default to jpg
                ext = 'jpg'
        
        # Generate a unique filename
        filename = f"{uuid.uuid4().hex}.{ext}"
        filepath = os.path.join(save_dir, filename)
        
        # Save image to disk
        with open(filepath, 'wb') as f:
            f.write(response.content)
        
        return filename, filepath
        
    except Exception as e:
        print(f"Error downloading image {img_url}: {str(e)}")
        return None, None

def extract_all_text(html_content):
    """Extract all text from HTML content"""
    # Simple regex-based extraction (a real implementation would use BeautifulSoup)
    text = re.sub(r'<[^>]+>', ' ', html_content)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def check_keyword_relevance(text, keywords, threshold=0.001):
    """Check if text contains keywords and calculate relevance"""
    text = text.lower()
    total_words = len(text.split())
    
    if total_words == 0:
        return False, 0, {}
    
    matches = {}
    total_matches = 0
    
    for keyword in keywords:
        keyword = keyword.lower()
        count = text.count(keyword)
        if count > 0:
            matches[keyword] = count
            total_matches += count
    
    relevance_score = total_matches / total_words if total_words > 0 else 0
    is_relevant = relevance_score >= threshold
    
    return is_relevant, total_matches, matches