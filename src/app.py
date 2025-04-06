import os
import json
import streamlit as st
import pandas as pd
import asyncio
import re
from PIL import Image
import requests
from io import BytesIO
import time

# Import the crawler from the same directory
from crawler import crawl_website, Crawl4AiClient

# Configure the page
st.set_page_config(page_title="Web Crawler Results", layout="wide")

def extract_page_information(results):
    """Extract relevant information from crawler results"""
    pages = []
    print("Extracting page information...")
    for result in results:
        page = {
            "content": result.get("cleaned_html", "No content available"),
            "title": result.get("metadata", {}).get("title", "No title available"),
            "images": result.get("media", {}).get("images", []),
            "internal_links": result.get("links", {}).get("internal", []),
            "external_links": result.get("links", {}).get("external", []),
        }
        pages.append(page)
    return pages

def get_plaintext(content):
    """Extract plain text from HTML content with paragraph structure preserved and headers/footers removed"""
    if not content:
        return "No content available"
    
    try:
        # Use BeautifulSoup for better HTML parsing
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(content, 'html.parser')
        
        # Remove script, style, and metadata elements
        for element in soup(['script', 'style', 'head', 'title', 'meta', '[document]']):
            element.extract()
        
        # Remove header, footer, and navigation elements
        for element in soup.select('header, footer, nav, .header, .footer, .navigation, .nav, .menu, .sidebar, #header, #footer, #nav, #menu, #sidebar, [class*="header"], [class*="footer"], [class*="nav"], [id*="header"], [id*="footer"], [id*="nav"]'):
            element.extract()
        
        # Handle paragraph breaks - add newlines after these elements
        for tag in soup.find_all(['p', 'div', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'br', 'li']):
            tag.append('\n\n')
        
        # Handle list items - add bullet points
        for tag in soup.find_all('li'):
            tag.insert_before('• ')
            
        # Get the text with preserved spacing from specific elements
        text = soup.get_text()
        
        # Normalize line breaks and remove excessive whitespace
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = '\n'.join(chunk for chunk in chunks if chunk)
        
        # Fix multiple consecutive newlines (more than 2)
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        # Decode HTML entities
        text = text.replace('&nbsp;', ' ')
        text = text.replace('&amp;', '&')
        text = text.replace('&lt;', '<')
        text = text.replace('&gt;', '>')
        text = text.replace('&quot;', '"')
        text = text.replace('&#39;', "'")
        
        return text
        
    except ImportError:
        # Fallback if BeautifulSoup is not available
        # Remove HTML tags but try to preserve some structure
        # First remove headers and footers
        clean_text = re.sub(r'<header[^>]*>.*?</header>', '', content, flags=re.DOTALL)
        clean_text = re.sub(r'<footer[^>]*>.*?</footer>', '', clean_text, flags=re.DOTALL)
        clean_text = re.sub(r'<nav[^>]*>.*?</nav>', '', clean_text, flags=re.DOTALL)
        
        # Then handle other HTML elements
        clean_text = re.sub(r'<br[^>]*>', '\n', clean_text)
        clean_text = re.sub(r'</p>\s*<p>', '\n\n', clean_text)
        clean_text = re.sub(r'<h[1-6][^>]*>', '\n\n', clean_text)
        clean_text = re.sub(r'</h[1-6]>', '\n', clean_text)
        clean_text = re.sub(r'<li[^>]*>', '\n• ', clean_text)
        clean_text = re.sub(r'<[^>]+>', ' ', clean_text)
        
        # Fix whitespace but preserve line breaks
        clean_text = re.sub(r' +', ' ', clean_text)
        clean_text = re.sub(r'\n+', '\n\n', clean_text)
        
        # Decode HTML entities
        clean_text = clean_text.replace('&nbsp;', ' ')
        clean_text = clean_text.replace('&amp;', '&')
        clean_text = clean_text.replace('&lt;', '<')
        clean_text = clean_text.replace('&gt;', '>')
        clean_text = clean_text.replace('&quot;', '"')
        clean_text = clean_text.replace('&#39;', "'")
        
        # Trim whitespace
        clean_text = clean_text.strip()
        
        return clean_text   
def perform_keyword_analysis(pages, keywords):
    """Analyze content for keyword matches"""
    results = []
    
    for i, page in enumerate(pages):
        content = page["content"].lower()
        matches = {}
        
        for keyword in keywords:
            keyword = keyword.lower().strip()
            if keyword:
                count = content.count(keyword)
                if count > 0:
                    matches[keyword] = count
        
        if matches:
            results.append({
                "page_index": i,
                "title": page["title"],
                "matches": matches,
                "total_matches": sum(matches.values())
            })
    
    return sorted(results, key=lambda x: x["total_matches"], reverse=True)

def display_image(image_data):
    """Display an image using the image data"""
    if not image_data or not isinstance(image_data, dict):
        st.warning("Invalid image data")
        return

    image_url = image_data.get('src')
    if not image_url:
        st.warning("No image URL found")
        return
        
    try:
        response = requests.get(image_url, timeout=5)
        img = Image.open(BytesIO(response.content))
        st.image(img, width=200)
    except Exception as e:
        st.warning(f"Could not load image")

async def fetch_data_from_api(url, keywords, max_depth, max_pages):
    """Fetch data directly from the Crawl4AI API"""
    with st.spinner(f"Crawling {url}..."):
        try:
            progress_placeholder = st.empty()
            
            def progress_callback(current, total, matched, images, status):
                progress_placeholder.progress(current/total if total > 0 else 0)
                progress_placeholder.text(f"{status} - {current}/{total} pages, {matched} relevant pages, {images} images")
            
            client = Crawl4AiClient()
            crawl_results = []
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
            task_id = client.submit_crawl(url, crawl_config)
            while True:
                status = client.get_task_status(task_id)
                if status["status"] == "completed":
                    print("Crawl completed")
                    st.session_state.crawl_results = status["results"]
                    break
                elif status["status"] == "failed":
                    raise Exception(f"Crawl task failed: {status.get('error', 'Unknown error')}")
            
            return True
        
        except Exception as e:
            st.error(f"Error during crawl: {str(e)}")
            return False

def main():
    st.title("Web Crawler Results")
    
    # Initialize session state for storing results
    if 'crawl_results' not in st.session_state:
        st.session_state.crawl_results = []
    
    # Sidebar for controls
    with st.sidebar:
        st.header("Controls")
        
        # New crawl section
        st.subheader("Start New Crawl")
        url = st.text_input("URL to crawl", "https://example.com")
        keywords = st.text_input("Keywords (comma-separated)", 
                                "sustainability, environment, green, eco")
        max_depth = st.slider("Max crawl depth", 1, 5, 2)
        max_pages = st.slider("Max pages to crawl", 5, 100, 25)
        
        if st.button("Start Crawling"):
            keywords_list = [k.strip() for k in keywords.split(",") if k.strip()]
            # Add a try-except to handle asyncio errors in Streamlit
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                success = loop.run_until_complete(fetch_data_from_api(url, keywords_list, max_depth, max_pages))
                if success:
                    st.success("Crawl completed!")
                    st.rerun()
            except Exception as e:
                st.error(f"Error during crawl: {str(e)}")
        
        # # Keyword analysis section
        # st.subheader("Keyword Analysis")
        # analysis_keywords = st.text_input("Analysis keywords (comma-separated)",
        #                                  "nature, wildlife, conservation")
        # run_analysis = st.button("Run Analysis")

    # Process and display results
    if not st.session_state.crawl_results:
        st.info("No crawl results yet. Start a new crawl using the sidebar controls.")
        return
    
    # Extract page information from the API results
    pages = extract_page_information(st.session_state.crawl_results)
    
    # Display summary
    st.header(f"Crawl Summary: {len(pages)} Pages Found")
    
    # Run keyword analysis if requested
    # if run_analysis:
    #     analysis_keywords_list = [k.strip() for k in analysis_keywords.split(",") if k.strip()]
    #     analysis_results = perform_keyword_analysis(pages, analysis_keywords_list)
        
    #     if analysis_results:
    #         st.subheader("Keyword Analysis Results")
            
    #         # Create a DataFrame for better visualization
    #         analysis_data = []
    #         for result in analysis_results:
    #             row = {
    #                 "Title": result["title"],
    #                 "Total Matches": result["total_matches"]
    #             }
    #             for keyword, count in result["matches"].items():
    #                 row[f"'{keyword}'"] = count
    #             analysis_data.append(row)
            
    #         analysis_df = pd.DataFrame(analysis_data)
    #         st.dataframe(analysis_df)
    #     else:
    #         st.info("No keyword matches found.")
    
    # Display page results
    for i, page in enumerate(pages):
        with st.expander(f"Page {i+1}: {page['title']}"):
            # Create tabs for different content sections
            content_tab, links_tab, images_tab = st.tabs(["Content", "Links & Metadata", "Images"])
            
            # Content tab
            with content_tab:
                st.subheader("Content Preview")
                st.text_area("",get_plaintext(page["content"]), height=800)
            
            # Links & Metadata tab
            with links_tab:
                # Display metadata
                st.subheader("Page Metadata")
                st.write(f"**Title:** {page['title']}")
                
                # Display internal links
                if page["internal_links"]:
                    st.subheader("Internal Links")
                    for link in page["internal_links"][:100]:
                        url = link.get("href", "")
                        text = link.get("text", url)
                        st.write(f"- [{text}]({url})")
                    
                    if len(page["internal_links"]) > 100:
                        st.write(f"... and {len(page['internal_links']) - 10} more links")
                
                # Display external links if available
                if page.get("external_links"):
                    st.subheader("External Links")
                    for link in page["external_links"][:10]:
                        url = link.get("href", "")
                        text = link.get("text", url)
                        st.write(f"- [{text}]({url})")
                    
                    if len(page["external_links"]) > 10:
                        st.write(f"... and {len(page['external_links']) - 10} more links")
            
            # Images tab
            with images_tab:
                if page["images"]:
                    st.subheader("Page Images")
                    
                    # Create a grid layout for images
                    cols = st.columns(3)
                    for j, img in enumerate(page["images"][:100]):
                        with cols[j % 3]:
                            alt_text = img.get("alt", img.get("alt_text", "No description"))
                            st.caption(alt_text)
                            display_image(img)
                    
                    if len(page["images"]) > 100:
                        st.write(f"... and {len(page['images']) - 9} more images")
                else:
                    st.info("No images found on this page")
                    
if __name__ == "__main__":
    main()