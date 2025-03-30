"""
Utility functions for the web crawler application.
Contains helper functions for file naming, image processing, and text extraction.
"""
import re
import os
import requests
from urllib.parse import urljoin, urlparse
import uuid
from bs4 import BeautifulSoup, Comment

def sanitize_filename(url):
    """
    Convert URL to a valid filename by removing invalid characters.
    
    Args:
        url (str): The URL to sanitize
        
    Returns:
        str: A filename-safe version of the URL
    """
    # Remove protocol and replace invalid filename chars
    sanitized = re.sub(r'^https?://', '', url)
    sanitized = re.sub(r'[\\/*?:"<>|]', '_', sanitized)
    sanitized = re.sub(r'[. ]', '-', sanitized)
    # Limit length to avoid file system issues
    return sanitized[:100] if len(sanitized) > 100 else sanitized

def is_valid_image_url(url):
    """
    Check if URL points to a valid image file.
    
    Args:
        url (str): The URL to check
        
    Returns:
        bool: True if the URL appears to be an image, False otherwise
    """
    if not url:
        return False
    
    # Check if URL ends with a common image extension
    image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg', '.bmp']
    parsed = urlparse(url)
    path = parsed.path.lower()
    
    return any(path.endswith(ext) for ext in image_extensions)

def download_image(img_url, base_url, save_dir):
    """
    Download an image from URL and save to specified directory.
    
    Args:
        img_url (str): The image URL to download
        base_url (str): The base URL of the page where the image was found
        save_dir (str): Directory to save the downloaded image
        
    Returns:
        tuple: (filename, filepath) if successful, (None, None) if failed
    """
    try:
        # Join relative URLs with base URL
        if not img_url.startswith(('http://', 'https://')):
            img_url = urljoin(base_url, img_url)
            
        # Generate a unique filename
        img_name = f"{uuid.uuid4().hex}.{img_url.split('.')[-1]}"
        if '?' in img_name:
            img_name = img_name.split('?')[0]
            
        img_path = os.path.join(save_dir, img_name)
        
        # Download the image
        response = requests.get(img_url, stream=True, timeout=10)
        if response.status_code == 200:
            with open(img_path, 'wb') as f:
                for chunk in response.iter_content(1024):
                    f.write(chunk)
            return img_name, img_path
    except Exception as e:
        print(f"Failed to download image {img_url}: {e}")
        
    return None, None

def extract_all_text(html_content, url):
    """
    Extract main content text from HTML while excluding navigation, headers, footers, etc.
    Preserves paragraph structure for better readability.
    
    Args:
        html_content: Raw HTML content
        url: Source URL
        
    Returns:
        str: Extracted main content with preserved paragraph structure
    """
    if not html_content:
        return ""
    
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Remove common navigation, header and footer elements
    for element in soup.select('nav, header, footer, .menu, .navigation, .sidebar, .widget, .ads, .breadcrumbs'):
        element.extract()
    
    # Remove script, style, form elements
    for tag in ['script', 'style', 'form', 'iframe', 'noscript']:
        for element in soup.find_all(tag):
            element.extract()
            
    # Remove comment elements
    for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
        comment.extract()
    
    # Try to find the main content element
    main_content = None
    
    # Look for common content containers by ID and class
    content_indicators = [
        'article', 'post', 'content', 'main', 'body-content', 'entry', 'story'
    ]
    
    # First try to get content by ID
    for indicator in content_indicators:
        element = soup.find(id=re.compile(f'.*{indicator}.*', re.I))
        if element:
            main_content = element
            break
    
    # If not found, try by class
    if not main_content:
        for indicator in content_indicators:
            elements = soup.find_all(class_=re.compile(f'.*{indicator}.*', re.I))
            if elements:
                # Use the largest content block by text length
                main_content = max(elements, key=lambda x: len(x.get_text()))
                break
    
    # If still not found, use the main tag, article tag or body as fallback
    if not main_content:
        main_content = soup.find('main') or soup.find('article') or soup.body
    
    if not main_content:
        # Last resort: use body if nothing else worked
        main_content = soup.body if soup.body else soup
    
    # Extract paragraphs with proper formatting
    paragraphs = []
    
    # Get text from paragraphs with proper spacing
    for p in main_content.find_all(['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
        text = p.get_text(strip=True)
        if text and len(text) > 15:  # Skip very short lines likely to be UI elements
            # Add extra newline before headings
            if p.name.startswith('h'):
                paragraphs.append("")  # Empty line before heading
                paragraphs.append(text)
                paragraphs.append("")  # Empty line after heading
            else:
                paragraphs.append(text)
    
    # If we didn't get paragraphs, try divs that might contain paragraphs
    if not paragraphs:
        for div in main_content.find_all('div'):
            text = div.get_text(strip=True)
            if text and len(text) > 100:  # Only substantial divs
                paragraphs.append(text)
    
    # Join with double newlines for better paragraph separation
    return "\n\n".join(paragraphs)

def check_keyword_relevance(text, keywords, threshold=0.001):
    """
    Check if the text contains keyword matches to be considered relevant.
    
    Args:
        text (str): The text to analyze
        keywords (list): List of keywords to search for
        threshold (float): Minimum relevance score threshold
        
    Returns:
        tuple: (is_relevant, match_count, keyword_matches_dict)
    """
    if not text or not keywords:
        return False, 0, {}
    
    text = text.lower()
    match_count = 0
    total_words = len(text.split())
    keyword_matches = {}
    
    for keyword in keywords:
        keyword = keyword.lower()
        # Count occurrences of the keyword in the text - more flexible matching
        # 1. Try exact word match
        exact_matches = len(re.findall(r'\b' + re.escape(keyword) + r'\b', text))
        # 2. Try partial match (for compound words)
        partial_matches = text.count(keyword)
        # Use the higher count
        count = max(exact_matches, partial_matches)
        
        match_count += count
        keyword_matches[keyword] = count
    
    # If any keywords were found at all, consider it relevant
    if match_count > 0:
        is_relevant = True
    else:
        # Calculate relevance score - matches per word in document
        score = match_count / total_words if total_words > 0 else 0
        is_relevant = score >= threshold
    
    return is_relevant, match_count, keyword_matches