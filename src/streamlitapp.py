import streamlit as st
import pandas as pd
import altair as alt

def display_images_tab(results):
    """Display images from Crawl4AI results"""
    st.subheader("Extracted Images")
    
    all_images = [
        img for page in results['results']
        for img in page['images']
    ]
    
    if all_images:
        cols = st.columns(3)
        for idx, img_url in enumerate(all_images[:30]):
            with cols[idx % 3]:
                try:
                    st.image(img_url, caption=f"Image {idx+1}", use_column_width=True)
                    st.caption(f"Source: {img_url}")
                except Exception as e:
                    st.error(f"Failed to load image: {str(e)[:50]}")
    else:
        st.warning("No images extracted")


def display_analysis_tab(results, keywords_list):
    """Visualize semantic relevance scores"""
    st.subheader("Semantic Relevance Analysis")
    
    if results['results']:
        df = pd.DataFrame({
            'Page': [res['title'] for res in results['results']],
            'Relevance Score': [res['relevance_score'] for res in results['results']],
            'Keywords': [", ".join(res['keyword_matches']) for res in results['results']]
        })
        
        chart = alt.Chart(df).mark_circle().encode(
            x='Page:N',
            y='Relevance Score:Q',
            size='Relevance Score:Q',
            color='Keywords:N',
            tooltip=['Page', 'Relevance Score', 'Keywords']
        ).properties(height=400)
        
        st.altair_chart(chart, use_container_width=True)

def display_images_tab(results):
    """Display images from Crawl4AI results"""
    st.subheader("Extracted Images")
    
    all_images = [
        img for page in results['results']
        for img in page['images']
    ]
    
    if all_images:
        cols = st.columns(3)
        for idx, img_url in enumerate(all_images[:30]):
            with cols[idx % 3]:
                try:
                    st.image(img_url, caption=f"Image {idx+1}", use_column_width=True)
                    st.caption(f"Source: {img_url}")
                except Exception as e:
                    st.error(f"Failed to load image: {str(e)[:50]}")
    else:
        st.warning("No images extracted")
