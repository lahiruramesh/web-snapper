"""
Visualization components for the Streamlit web crawler app.
Contains functions for displaying data and creating interactive visualizations.
"""
import re
import streamlitapp as st
import pandas as pd
import altair as alt
from PIL import Image
import os
import glob

def display_pages_tab(results, keywords_list):
    """
    Display the "Relevant Pages" tab content.
    
    Args:
        results (dict): The crawler results dict
        keywords_list (list): List of keywords for highlighting
    """
    st.subheader("Pages Matching Keywords")
    
    if not results['results'] or len(results['results']) == 0:
        st.warning("No pages matched your keywords")
        return
        
    pages_df = pd.DataFrame([{
        'URL': result['url'],
        'Title': result['title'],
        'Depth': result['depth'],
        'Keyword Matches': result['keyword_matches'],
        'Relevance Score': result['relevance_score'],
        'Images Found': len(result['images'])
    } for result in results['results']])
    
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
    
    # Display highlighted content
    with st.expander("Page Content (Keywords Highlighted)", expanded=False):
        highlighted_html = highlight_keywords(selected_page['text'], keywords_list)
        st.markdown(highlighted_html, unsafe_allow_html=True)

def display_images_tab(results):
    """Display the images tab with extracted images"""
    st.subheader("Extracted Images")
    
    # Get all image files
    image_files = glob.glob(os.path.join(results['images_dir'], "*"))
    
    if image_files:
        # Create filter for images
        st.write(f"Found {len(image_files)} images")
        
        # Create a map of image paths to their source pages for quick lookup
        image_source_map = {}
        for page in results['results']:
            for img in page['images']:
                # Store normalized paths to handle any path differences
                norm_path = os.path.normpath(img['path'])
                image_source_map[norm_path] = {
                    'page_title': page['title'],
                    'page_url': page['url'],
                    'alt_text': img['alt_text']
                }
        
        # Display images in grid with 3 columns
        cols = st.columns(3)
        for i, img_path in enumerate(image_files[:30]):  # Limit to first 30 images to avoid overload
            try:
                # Normalize the path for comparison
                norm_path = os.path.normpath(img_path)
                
                img = Image.open(img_path)
                with cols[i % 3]:
                    st.image(img, caption=os.path.basename(img_path), use_column_width=True)
                    
                    # Find source page info from our map
                    if norm_path in image_source_map:
                        source_info = image_source_map[norm_path]
                        st.caption(f"From: [{source_info['page_title']}]({source_info['page_url']})")
                        if source_info['alt_text']:
                            st.caption(f"Alt text: {source_info['alt_text']}")
                    else:
                        st.caption("Source page unknown")
            except Exception as e:
                cols[i % 3].error(f"Could not load image: {str(e)[:50]}...")
        
        if len(image_files) > 30:
            st.info(f"Showing first 30 of {len(image_files)} images. All images are saved in the results directory.")
    else:
        st.warning("No images were extracted that matched your keywords")
 
def display_analysis_tab(results, keywords_list):
    """
    Display the "Content Analysis" tab content.
    
    Args:
        results (dict): The crawler results dict
        keywords_list (list): List of keywords for analysis
    """
    st.subheader("Keyword Analysis")
    
    if not results['results'] or len(results['results']) == 0:
        st.warning("No pages matched your keywords")
        return
        
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
    
    if not keyword_data:
        st.warning("No keyword occurrences found in the crawled pages")
        return
        
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

def display_summary_tab(results):
    """
    Display the "Summary" tab content.
    
    Args:
        results (dict): The crawler results dict
    """
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

def highlight_keywords(text, keywords):
    """
    Highlight keywords in text using HTML.
    
    Args:
        text (str): Text to process
        keywords (list): Keywords to highlight
        
    Returns:
        str: HTML with highlighted keywords
    """
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