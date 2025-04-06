import streamlit as st
import pandas as pd
import altair as alt

def display_analysis_tab(results, keywords_list):
    """Visualize semantic relevance scores from Crawl4AI"""
    st.subheader("Semantic Relevance Analysis")
    
    df = pd.DataFrame({
        'Page': [res['title'] for res in results['results']],
        'Relevance Score': [res['relevance'] for res in results['results']],
        'Matched Keywords': [', '.join(res['keywords']) for res in results['results']]
    })
    
    chart = alt.Chart(df).mark_bar().encode(
        x='Relevance Score:Q',
        y='Page:N',
        color='Matched Keywords:N',
        tooltip=['Page', 'Relevance Score', 'Matched Keywords']
    ).properties(height=500)
    
    st.altair_chart(chart, use_container_width=True)
