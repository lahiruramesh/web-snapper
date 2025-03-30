"""
Web Crawler & Image Extractor Application
A Streamlit app for crawling websites and extracting relevant content and images.
"""
import streamlit as st
import asyncio
import time
import re
import os
import glob
import pandas as pd
import altair as alt
from PIL import Image

from crawler import crawl_website

def main():
    """Main application entry point"""
    # Initialize session state to store results between reruns
    if 'has_results' not in st.session_state:
        st.session_state.has_results = False
        st.session_state.results = None
        st.session_state.keywords_list = []

    st.set_page_config(page_title="Web Crawler with Image Extraction", layout="wide")

    st.title("Web Crawler & Image Extractor")
    st.write("Enter a URL to crawl and extract images and content with keyword filtering")

    # Only show the form if we don't have results already
    if not st.session_state.has_results:
        display_input_form()
    else:
        # If we have results in the session state, display them
        display_results()

    st.markdown("---")
    st.caption("Web Crawler with Image Extraction | Built with Streamlit and crawl4ai")

def display_input_form():
    """Display the input form for crawler parameters"""
    with st.form("crawler_form"):
        col1, col2 = st.columns(2)
        with col1:
            url = st.text_input("Website URL", "https://www.example.com")
            max_depth = st.slider("Crawl Depth", 1, 5, 2)
        with col2:
            keywords = st.text_area("Relevance Keywords (one per line)", 
                                  "sustainability\nenvironment\ngreen\neco")
            max_pages = st.number_input("Max Pages to Crawl", 1, 100, 25)
        
        submit_button = st.form_submit_button("Start Crawling")
        
        if submit_button:
            process_crawler_submission(url, keywords, max_depth, max_pages)

def process_crawler_submission(url, keywords, max_depth, max_pages):
    """Process the crawler form submission"""
    keywords_list = [k.strip() for k in keywords.split('\n') if k.strip()]
    st.session_state.keywords_list = keywords_list
    
    # Show progress container
    progress_container = st.container()
    
    with progress_container:
        st.subheader("Crawl Progress")
        progress_bar = st.progress(0)
        status_text = st.empty()
        status_text.text("Setting up crawler...")
        
        # Add counters for real-time updates
        col1, col2, col3 = st.columns(3)
        pages_counter = col1.empty()
        relevant_pages_counter = col2.empty()
        images_counter = col3.empty()
        
        pages_counter.metric("Pages Crawled", "0")
        relevant_pages_counter.metric("Relevant Pages", "0")
        images_counter.metric("Images Found", "0")
    
    # Run the crawler
    try:
        # Initialize the crawler with a callback for progress
        status_text.text("Starting crawler...")
        
        start_time = time.time()
        
        # Create a callback for progress updates
        def progress_callback(current_page, total_pages, matched_pages, matched_images, status="Crawling"):
            """Callback to update progress during crawling"""
            # Update progress bar (ensure it stays between 0-100%)
            progress_value = min(current_page / max_pages, 1.0) if max_pages > 0 else 0
            progress_bar.progress(progress_value)
            
            # Update status text
            status_text.text(f"Status: {status} - Page {current_page}/{max_pages}")
            
            # Update metrics
            pages_counter.metric("Pages Crawled", str(current_page))
            relevant_pages_counter.metric("Relevant Pages", str(matched_pages))
            images_counter.metric("Images Found", str(matched_images))
            
            # Allow UI to update
            time.sleep(0.1)
        
        # Run the actual crawler with progress callback
        results = asyncio.run(crawl_website(
            url, 
            keywords_list, 
            max_depth, 
            max_pages, 
            progress_callback=progress_callback
        ))
        
        # Update final metrics
        progress_bar.progress(1.0)
        status_text.text(f"Crawling complete in {time.time() - start_time:.1f} seconds!")
        pages_counter.metric("Pages Crawled", str(results['total_pages']))
        relevant_pages_counter.metric("Relevant Pages", str(results['matched_pages']))
        images_counter.metric("Images Found", str(results['matched_images']))
        
        # Store results in session state
        st.session_state.results = results
        st.session_state.has_results = True
        
        # Force rerun to display results
        st.rerun()
        
    except Exception as e:
        st.error(f"An error occurred during crawling: {str(e)}")
        st.exception(e)
def display_results():
    """Display the crawler results"""
    results = st.session_state.results
    keywords_list = st.session_state.keywords_list
    
    # Add a button to start a new crawl
    if st.button("Start New Crawl"):
        st.session_state.has_results = False
        st.session_state.results = None
        st.session_state.keywords_list = []
        st.rerun()
        return
    
    # Display tabs for different sections
    tabs = st.tabs(["Pages", "Images", "Analysis", "Summary"])
    
    with tabs[0]:
        display_pages_tab(results, keywords_list)
    with tabs[1]:
        display_images_tab(results)
    with tabs[2]:
        display_analysis_tab(results, keywords_list)
    with tabs[3]:
        display_summary_tab(results, keywords_list)

def display_pages_tab(results, keywords_list):
    """Display the pages tab with crawled content"""
    st.subheader("Pages Matching Keywords")
    
    if len(results['results']) > 0:
        # Create a dataframe for better display
        pages_df = pd.DataFrame([{
            'URL': result['url'],
            'Title': result['title'],
            'Depth': result['depth'],
            'Keyword Matches': result['keyword_matches'],
            'Relevance Score': result['relevance_score'],
            'Images Found': len(result['images'])
        } for result in results['results']])
        
        # Add sorting
        st.dataframe(
            pages_df,
            column_config={
                "URL": st.column_config.LinkColumn("URL"),
                "Relevance Score": st.column_config.NumberColumn(
                    "Relevance Score",
                    format="%.4f",
                ),
            },
            hide_index=True,
            use_container_width=True
        )
        
        # Display page content for selected page
        selected_page_idx = st.selectbox(
            "Select a page to view details:",
            range(len(results['results'])),
            format_func=lambda i: f"{results['results'][i]['title']} ({results['results'][i]['url']})"
        )
        
        selected_page = results['results'][selected_page_idx]
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.subheader(f"Page Details: {selected_page['title']}")
            st.write(f"URL: [{selected_page['url']}]({selected_page['url']})")
            st.write(f"Depth: {selected_page['depth']}")
            st.write(f"Status: {selected_page['status_code']}")
            st.write(f"Keyword Matches: {selected_page['keyword_matches']}")
            st.write(f"Relevance Score: {selected_page['relevance_score']:.4f}")
        
        with col2:
            # Show page images if available
            if selected_page['images']:
                st.write(f"Images on this page: {len(selected_page['images'])}")
                # Display a sample image
                try:
                    sample_img = Image.open(selected_page['images'][0]['path'])
                    st.image(sample_img, caption="Sample image from page", width=200)
                except Exception:
                    st.write("Preview not available")
        
        # Function to highlight keywords in text
        def highlight_keywords(text, keywords):
            if not text:
                return "No content available"
            
            highlighted_text = text
            
            # Apply HTML highlighting for each keyword
            for keyword in keywords:
                if not keyword:
                    continue
                
                pattern = re.compile(r'\b' + re.escape(keyword) + r'\b', re.IGNORECASE)
                highlighted_text = pattern.sub(f'<mark style="background-color: #FFFF00; padding: 0px 2px; border-radius: 2px;">{keyword}</mark>', highlighted_text)
            
            # Convert newlines to <br> tags
            highlighted_text = highlighted_text.replace('\n', '<br>')
            
            return f'<div style="max-height: 400px; overflow-y: auto; padding: 10px; border: 1px solid #ddd; border-radius: 5px;">{highlighted_text}</div>'
        
        # Display highlighted content
        with st.expander("Page Content (Keywords Highlighted)", expanded=False):
            highlighted_html = highlight_keywords(selected_page['text'], keywords_list)
            st.markdown(highlighted_html, unsafe_allow_html=True)
    else:
        st.warning("No pages matched your keywords")

def display_images_tab(results):
    """Display the images tab with extracted images"""
    st.subheader("Extracted Images")
    
    # Get all image files
    image_files = glob.glob(os.path.join(results['images_dir'], "*"))
    
    if image_files:
        # Create filter for images
        st.write(f"Found {len(image_files)} images")
        
        # Display images in grid with 3 columns
        cols = st.columns(3)
        for i, img_path in enumerate(image_files[:30]):  # Limit to first 30 images to avoid overload
            try:
                img = Image.open(img_path)
                with cols[i % 3]:
                    st.image(img, caption=os.path.basename(img_path), use_column_width=True)
                    
                    # Find which page this image belongs to
                    for page in results['results']:
                        for page_img in page['images']:
                            if page_img['path'] == img_path:
                                st.caption(f"From: {page['title']}")
                                break
            except Exception as e:
                cols[i % 3].error(f"Could not load image: {str(e)[:50]}...")
        
        if len(image_files) > 30:
            st.info(f"Showing first 30 of {len(image_files)} images. All images are saved in the results directory.")
    else:
        st.warning("No images were extracted that matched your keywords")

def display_analysis_tab(results, keywords_list):
    """Display the analysis tab with keyword statistics"""
    st.subheader("Keyword Analysis")
    
    if len(results['results']) > 0:
        # Create data for chart
        keyword_data = []
        for keyword in keywords_list:
            for page_idx, page in enumerate(results['results']):
                page_text = page['text'].lower()
                count = len(re.findall(r'\b' + re.escape(keyword.lower()) + r'\b', page_text))
                if count > 0:
                    keyword_data.append({
                        "Keyword": keyword,
                        "Page": page['title'],
                        "Count": count
                    })
        
        if keyword_data:
            # Create a bar chart
            keyword_df = pd.DataFrame(keyword_data)
            
            chart = alt.Chart(keyword_df).mark_bar().encode(
                x=alt.X("Count:Q", title="Occurrences"),
                y=alt.Y("Page:N", title="Page"),
                color=alt.Color("Keyword:N", title="Keyword"),
                tooltip=["Page", "Keyword", "Count"]
            ).properties(
                title="Keyword Occurrences by Page",
                height=min(500, len(results['results']) * 40)
            )
            
            st.altair_chart(chart, use_container_width=True)
        else:
            st.warning("No keyword occurrences found in the crawled pages")
    else:
        st.warning("No pages matched your keywords")

def display_summary_tab(results, keywords_list):
    """Display the summary tab with overall crawl statistics"""
    st.subheader("Crawl Summary")
    
    # Try to read the summary file
    try:
        with open(results['summary_file'], 'r') as f:
            summary_content = f.read()
        st.text_area("Summary Report", summary_content, height=400)
        
        # Add download button for summary
        with open(results['summary_file'], 'r') as f:
            st.download_button(
                "Download Summary Report",
                f,
                file_name="web_crawler_summary.txt",
                mime="text/plain"
            )
    except Exception as e:
        st.error(f"Could not read summary file: {str(e)}")

if __name__ == "__main__":
    main()