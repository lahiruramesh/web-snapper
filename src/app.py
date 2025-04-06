import os
import requests
import streamlit as st
import time
import pandas as pd
import json
import re
import base64
from io import BytesIO
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def main():
    st.title("Web Snapper with Crawl4AI Integration")
    
    # API Configuration
    CRAWL4AI_API_URL = os.getenv("CRAWL4AI_API_URL", "http://localhost:11235")
    API_TOKEN = os.getenv("CRAWL4AI_API_TOKEN")
    
    # Debug the current state
    if st.sidebar.checkbox("Show Debug Info", key="show_debug_checkbox"):
        st.sidebar.write("Session State:")
        st.sidebar.json({k: v for k, v in st.session_state.items()})
    
    # Initialize session state
    if 'task_id' not in st.session_state:
        st.session_state.task_id = None
    
    if 'results' not in st.session_state:
        st.session_state.results = None
        
    if 'kill_crawl' not in st.session_state:
        st.session_state.kill_crawl = False
        
    if 'completed' not in st.session_state:
        st.session_state.completed = False
    
    # Add reset button
    col1, col2 = st.columns([3, 1])
    with col2:
        if st.button("Reset", key="reset_button"):
            st.session_state.task_id = None
            st.session_state.results = None
            st.session_state.completed = False
            st.session_state.kill_crawl = False
            st.rerun()
    
    # Crawl form - only show if not in a crawling state
    if not st.session_state.task_id or st.session_state.completed:
        with st.form("crawl_form"):
            url = st.text_input("Website URL", "https://www.naturepreserve.co/", key="url_input")
            keywords = st.text_input("Keywords (comma-separated)", "", key="keywords_input")
            max_depth = st.slider("Crawl Depth", 1, 5, 2)
            max_pages = st.slider("Maximum Pages", 5, 50, 10)
            submitted = st.form_submit_button("Start Crawl")
            
            if submitted:
                # Reset any previous state
                st.session_state.completed = False
                st.session_state.results = None
                
                keyword_list = [k.strip() for k in keywords.split(',') if k.strip()]
                
                payload = {
                    "urls": [url],
                    "extraction_config": {
                        "type": "cosine",  # API requires "type" not "mode"
                        "params": {
                            "semantic_filter": keywords,
                            "word_count_threshold": 50,
                            "max_dist": 0.25
                        }
                    },
                    "crawl_config": {
                        "max_depth": max_depth,
                        "max_pages": max_pages
                    }
                }
                
                with st.spinner("Sending request to API..."):
                    try:
                        response = requests.post(
                            f"{CRAWL4AI_API_URL}/crawl",
                            headers={"Authorization": f"Bearer {API_TOKEN}"} if API_TOKEN else {},
                            json=payload,
                            timeout=30
                        )
                        
                        if response.status_code == 200:
                            task_id = response.json()['task_id']
                            print(f"Crawl started successfully: {task_id}")
                            st.session_state.task_id = task_id
                            st.success(f"Crawl started! Task ID: {task_id}")
                            # Store keywords for later use
                            st.session_state.keywords = keyword_list
                            st.rerun()
                        else:
                            st.error(f"API Error: {response.text}")
                    except requests.exceptions.RequestException as e:
                        st.error(f"Connection error: {str(e)}")
    
    # Handle crawl state
    if st.session_state.task_id and not st.session_state.completed:
        # UI elements for crawl progress
        status_container = st.empty()
        progress_bar = st.progress(0)
        debug_container = st.empty()
        
        # Control buttons
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Cancel Crawl", key="cancel_button"):
                st.session_state.task_id = None
                st.session_state.completed = False
                st.rerun()
        with col2:
            if st.button("Force Stop (Emergency)", key="emergency_stop_button"):
                st.session_state.kill_crawl = True
                st.session_state.task_id = None
                st.session_state.completed = False
                st.warning("Crawl forcibly stopped")
                st.rerun()
        
        # Poll for task completion
        with st.spinner("Crawling in progress..."):
        # Keep correct API path - could be /task/ or /tasks/ depending on API version
            status_url = f"{CRAWL4AI_API_URL}/task/{st.session_state.task_id}"
            complete = False
            max_retries = 3
            retries = 0
            
            # Add timeout
            start_time = time.time()
            max_crawl_time = 300  # 5 minutes maximum crawl time
            
            # Track API call count to create unique keys
            api_call_count = 0
            api_call_count += 1
                
                # Check for emergency stop
            if st.session_state.kill_crawl:
                complete = True
                st.session_state.kill_crawl = False
            
            # Check for timeout
            if time.time() - start_time > max_crawl_time:
                st.warning(f"Crawl timed out after {max_crawl_time/60:.1f} minutes")
                st.session_state.task_id = None
                st.session_state.completed = False
            
            try:
                # Make API request with detailed debugging
                debug_container.text(f"Checking status at: {status_url}")
                
                response = requests.get(
                    status_url,
                    headers={"Authorization": f"Bearer {API_TOKEN}"} if API_TOKEN else {},
                    timeout=10
                )
                
                debug_container.text(f"Status code: {response.status_code}")
                
                if response.status_code == 200:
                    status = response.json()
                    # Fixed: Use get() method instead of attribute access
                    print("debug", status.get('status', 'unknown'))
                    
                    # Show raw status for debugging - USE UNIQUE KEY with counter
                    unique_checkbox_key = f"show_raw_api_res_checkbox_{api_call_count}"
                    if st.sidebar.checkbox("Show Raw API Response", key=unique_checkbox_key):
                        st.sidebar.json(status)
                    
                    # Update progress indicators
                    if 'pages_crawled' in status and 'total_pages' in status:
                        pages_crawled = status.get('pages_crawled', 0)
                        total_pages = max(1, status.get('total_pages', 1))
                        progress = min(0.99, pages_crawled / total_pages)
                        progress_bar.progress(progress)
                        
                        status_container.text(
                            f"Crawled: {pages_crawled} pages | " +
                            f"Matched: {status.get('relevant_pages', 0)} pages | " +
                            f"Images: {status.get('images_extracted', 0)}"
                        )
                    
                    # Check completion state with more detailed logging - CASE INSENSITIVE CHECK
                    state = status.get('status', '').upper()
                    debug_container.text(f"Current state: {state}")
                    
                    # FIX: Properly handle completion with case-insensitive comparison
                    if state.lower() == 'completed':
                        debug_container.text("✅ COMPLETION DETECTED!")
                        # Store results directly without waiting for rerun
                        result_data = status.get('results', {})
                        st.session_state.results = result_data
                        st.session_state.completed = True
                        progress_bar.progress(1.0)
                        
                        st.success("✅ Crawl completed successfully!")
                        # Display results if completed and results are available
                        if st.session_state.completed and st.session_state.results:
                            # Debug option to see raw results
                            if st.checkbox("Show Raw Result Data", key="show_raw_results"):
                                st.json(st.session_state.results)
                            
                            display_results(st.session_state.results, st.session_state.get('keywords', []))
                            
                            # Add an option to download results
                            if st.download_button(
                                label="Download Results as JSON",
                                data=json.dumps(st.session_state.results, indent=2),
                                file_name="crawl_results.json",
                                mime="application/json",
                                key="download_button"
                            ):
                                st.success("Results downloaded!")

                    
                    elif state.upper() == 'FAILED' or state.lower() == 'failed':
                        st.error(f"Crawl failed: {status.get('error', 'Unknown error')}")
                        st.session_state.task_id = None
                        st.session_state.completed = False

                else:
                    retries += 1
                    if retries >= max_retries:
                        st.error(f"Failed to get status: {response.text}")
                        try:
                            error_data = response.json()
                            st.error(f"Error details: {json.dumps(error_data)}")
                        except:
                            st.error(f"Status code: {response.status_code}")
                    
            except Exception as e:
                retries += 1
                if retries >= max_retries:
                    st.error(f"Error checking status: {str(e)}")
            
            # Final statement after loop has exited
            debug_container.text("Status polling has completed")        
    

def highlight_keywords(text, keywords):
    """Highlight keywords in text"""
    if not keywords or not text:
        return text
    
    highlighted = text
    for keyword in keywords:
        if not keyword:
            continue
        pattern = re.compile(r'\b' + re.escape(keyword) + r'\b', re.IGNORECASE)
        highlighted = pattern.sub(f"**{keyword}**", highlighted)
    
    return highlighted

def display_pdf_embed(pdf_data):
    """Display PDF embed from binary data"""
    try:
        if isinstance(pdf_data, bytes):
            base64_pdf = base64.b64encode(pdf_data).decode('utf-8')
        else:
            # If it's a base64 string already
            base64_pdf = pdf_data
            
        display_html = f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="100%" height="600" type="application/pdf"></iframe>'
        st.markdown(display_html, unsafe_allow_html=True)
    except Exception as e:
        st.error(f"Could not display PDF: {str(e)}")

def display_results(results, keywords):
    """Display the crawl results in a user-friendly format"""
    st.header("Crawl Results")
    
    # Create tabs for different content types
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["Pages", "Images", "PDFs", "Links", "Analysis"])
    
    # Pages Tab (Updated for new format)
    with tab1:
        st.subheader("Matched Pages")
        
        pages = results.get("pages", [])
        if pages:
            for i, page in enumerate(pages):
                # Check which format we're dealing with
                if "url" in page and "success" in page:  # New format
                    title = page.get("metadata", {}).get("title", "No title") if page.get("metadata") else "No title"
                    url = page.get("url", "No URL")
                    
                    with st.expander(f"{i+1}. {title}"):
                        st.write(f"**URL:** {url}")
                        
                        # Display metadata if available
                        if page.get("metadata"):
                            with st.expander("Metadata"):
                                st.json(page.get("metadata"))
                        
                        # Display extracted content with keyword highlights
                        if page.get("extracted_content"):
                            with st.expander("Content"):
                                highlighted_text = highlight_keywords(page.get("extracted_content"), keywords)
                                st.markdown(highlighted_text)
                        
                        # Display screenshot if available
                        if page.get("screenshot"):
                            with st.expander("Screenshot"):
                                try:
                                    # Assume screenshot is base64 or URL
                                    st.image(page.get("screenshot"), caption="Page Screenshot", use_column_width=True)
                                except:
                                    st.error("Could not display screenshot")
                        
                        # Show any errors
                        if not page.get("success"):
                            st.error(f"Error: {page.get('error_message', 'Unknown error')}")
                
                else:  # Old format
                    with st.expander(f"{i+1}. {page.get('metadata', {}).get('title', 'No title')}"):
                        st.write(f"**URL:** {page.get('url', 'No URL')}")
                        st.write(f"**Relevance Score:** {page.get('relevance_score', 0):.2f}")
                        
                        # Display matched keywords
                        if "matched_keywords" in page and page["matched_keywords"]:
                            st.write("**Matched Keywords:**")
                            for keyword, count in page["matched_keywords"].items():
                                st.write(f"- {keyword}: {count} occurrences")
                        
                        # Display page content with highlighted keywords
                        if "extracted_text" in page and page["extracted_text"]:
                            with st.expander("Content"):
                                highlighted_text = highlight_keywords(page["extracted_text"], keywords)
                                st.markdown(highlighted_text)
        else:
            st.warning("No pages matched your keywords")
    
    # Images Tab (Updated for new format)
    with tab2:
        st.subheader("Extracted Images")
        
        all_images = []
        
        # Collect images in both new and old format
        for page in results.get("pages", []):
            # New format
            if "media" in page and "images" in page.get("media", {}):
                for img in page.get("media", {}).get("images", []):
                    all_images.append({
                        "url": img.get("src", img.get("url", "")),
                        "alt": img.get("alt", "No description"),
                        "page_title": page.get("metadata", {}).get("title", "No title") if page.get("metadata") else "No title",
                        "page_url": page.get("url", "")
                    })
            # Old format
            elif "images" in page:
                for img in page.get("images", []):
                    all_images.append({
                        "url": img.get("url", ""),
                        "alt": img.get("alt", "No description"),
                        "page_title": page.get("metadata", {}).get("title", "No title"),
                        "page_url": page.get("url", "")
                    })
        
        if all_images:
            st.write(f"Found {len(all_images)} images")
            
            # Display images in grid
            cols = st.columns(3)
            for i, img in enumerate(all_images[:30]):  # Limit to 30 images
                try:
                    with cols[i % 3]:
                        st.image(img["url"], caption=img["alt"], use_column_width=True)
                        st.caption(f"From: [{img['page_title']}]({img['page_url']})")
                except Exception as e:
                    cols[i % 3].error(f"Could not load image: {str(e)[:50]}...")
        else:
            st.warning("No images were extracted")

    # PDFs Tab (New)
    with tab3:
        st.subheader("PDF Documents")
        
        all_pdfs = []
        
        # Collect PDFs from new format
        for page in results.get("pages", []):
            # Check for PDF in page
            if page.get("pdf"):
                all_pdfs.append({
                    "pdf_data": page.get("pdf"),
                    "page_title": page.get("metadata", {}).get("title", "No title") if page.get("metadata") else "No title",
                    "page_url": page.get("url", "")
                })
            
            # Check for PDFs in media
            if "media" in page and "pdfs" in page.get("media", {}):
                for pdf in page.get("media", {}).get("pdfs", []):
                    all_pdfs.append({
                        "url": pdf.get("url", ""),
                        "title": pdf.get("title", "No title"),
                        "page_title": page.get("metadata", {}).get("title", "No title") if page.get("metadata") else "No title",
                        "page_url": page.get("url", "")
                    })
            
            # Check for PDFs in downloaded_files
            if page.get("downloaded_files"):
                for file_path in page.get("downloaded_files", []):
                    if file_path.lower().endswith('.pdf'):
                        all_pdfs.append({
                            "file_path": file_path,
                            "page_title": page.get("metadata", {}).get("title", "No title") if page.get("metadata") else "No title",
                            "page_url": page.get("url", "")
                        })
        
        if all_pdfs:
            st.write(f"Found {len(all_pdfs)} PDF documents")
            
            for i, pdf in enumerate(all_pdfs):
                with st.expander(f"PDF #{i+1} from {pdf.get('page_title', 'Unknown page')}"):
                    st.write(f"**Source:** {pdf.get('page_url', 'Unknown URL')}")
                    
                    if "pdf_data" in pdf:
                        display_pdf_embed(pdf["pdf_data"])
                    elif "url" in pdf:
                        st.write(f"**PDF URL:** [{pdf.get('title', 'PDF Link')}]({pdf['url']})")
                        st.link_button("Open PDF", pdf['url'])
                    elif "file_path" in pdf:
                        st.write(f"**PDF File:** {pdf['file_path']}")
        else:
            st.warning("No PDF documents were found")

    # Links Tab (New)
    with tab4:
        st.subheader("Extracted Links")
        
        all_links = []
        
        # Collect links from pages
        for page in results.get("pages", []):
            page_links = []
            
            # New format
            if "links" in page:
                for link_type, links in page.get("links", {}).items():
                    for link in links:
                        page_links.append({
                            "url": link.get("href", link.get("url", "")),
                            "text": link.get("text", "No text"),
                            "type": link_type,
                            "page_url": page.get("url", ""),
                            "page_title": page.get("metadata", {}).get("title", "No title") if page.get("metadata") else "No title"
                        })
            
            all_links.extend(page_links)
        
        if all_links:
            st.write(f"Found {len(all_links)} links")
            
            # Create dataframe for links
            links_df = pd.DataFrame(all_links)
            
            # Add filters
            if len(links_df) > 0:
                # Filter by link type if available
                if "type" in links_df.columns:
                    link_types = ["All"] + sorted(links_df["type"].unique().tolist())
                    selected_type = st.selectbox("Filter by link type", link_types)
                    
                    if selected_type != "All":
                        links_df = links_df[links_df["type"] == selected_type]
                
                # Display links table
                st.dataframe(
                    links_df[["text", "url", "type", "page_title"]].rename(
                        columns={"text": "Link Text", "url": "URL", "type": "Type", "page_title": "Source Page"}
                    ),
                    use_container_width=True
                )
        else:
            st.warning("No links were extracted")
            
    # Analysis Tab (Updated for compatibility with both formats)
    with tab5:
        st.subheader("Keyword Analysis")
        
        # Create keyword frequency analysis - compatible with both formats
        keyword_counts = {}
        
        for page in results.get("pages", []):
            # For old format with matched_keywords
            if "matched_keywords" in page:
                for keyword, count in page.get("matched_keywords", {}).items():
                    if keyword in keyword_counts:
                        keyword_counts[keyword] += count
                    else:
                        keyword_counts[keyword] = count
            
            # For new format where keywords might be in metadata
            elif page.get("metadata", {}).get("keywords"):
                for keyword in page.get("metadata", {}).get("keywords", []):
                    if keyword in keyword_counts:
                        keyword_counts[keyword] += 1
                    else:
                        keyword_counts[keyword] = 1
        
        # If no keywords found but we have user keywords, check for them in content
        if not keyword_counts and keywords:
            for page in results.get("pages", []):
                content = page.get("extracted_content", page.get("extracted_text", ""))
                for keyword in keywords:
                    if keyword.lower() in content.lower():
                        count = content.lower().count(keyword.lower())
                        if keyword in keyword_counts:
                            keyword_counts[keyword] += count
                        else:
                            keyword_counts[keyword] = count
        
        if keyword_counts:
            # Create dataframe for chart
            df = pd.DataFrame({
                'Keyword': list(keyword_counts.keys()),
                'Occurrences': list(keyword_counts.values())
            })
            
            # Sort by occurrences
            df = df.sort_values('Occurrences', ascending=False)
            
            # Display chart
            st.bar_chart(df.set_index('Keyword'))
            
            # Display summary metrics
            col1, col2, col3 = st.columns(3)
            col1.metric("Total Pages", len(results.get("pages", [])))
            
            # Try different fields based on format
            matched_pages = results.get("relevant_pages", len(results.get("pages", [])))
            col2.metric("Matched Pages", matched_pages)
            
            # Count images
            image_count = 0
            for page in results.get("pages", []):
                # New format
                if "media" in page and "images" in page.get("media", {}):
                    image_count += len(page.get("media", {}).get("images", []))
                # Old format
                elif "images" in page:
                    image_count += len(page.get("images", []))
                    
            col3.metric("Images Extracted", image_count)
        else:
            st.warning("No keyword matches to analyze")

if __name__ == "__main__":
    main()