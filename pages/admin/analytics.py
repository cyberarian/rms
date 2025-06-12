"""Analytics dashboard for the admin panel"""
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import plotly.express as px

def render_analytics_dashboard():
    """Render the analytics dashboard in the admin panel"""
    st.header("📊 Analytics Dashboard")
    
    # Time period selector
    time_period = st.selectbox(
        "Select Time Period",
        ["Last 24 Hours", "Last 7 Days", "Last 30 Days", "All Time"],
        key="analytics_time_period"
    )
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Document Processing Stats")
        # Document processing metrics
        if 'uploaded_file_names' in st.session_state:
            total_docs = len(st.session_state.uploaded_file_names)
        else:
            total_docs = 0
            
        st.metric(
            "Total Documents",
            total_docs,
            help="Total number of documents processed"
        )
        
        # Mock data for OCR stats
        ocr_success_rate = 95.5
        st.metric(
            "OCR Success Rate",
            f"{ocr_success_rate}%",
            delta="1.2%",
            help="Percentage of documents successfully processed with OCR"
        )
    
    with col2:
        st.subheader("System Performance")
        # Response times metrics
        avg_response_time = 2.3
        st.metric(
            "Average Response Time",
            f"{avg_response_time}s",
            delta="-0.3s",
            help="Average time to process user queries"
        )
    
    # Mock data for document processing trend
    dates = pd.date_range(end=datetime.now(), periods=30, freq='D')
    data = {
        'date': dates,
        'documents_processed': [int(i/2) for i in range(30)],
        'ocr_used': [int(i/3) for i in range(30)]
    }
    df = pd.DataFrame(data)

    # Create line chart
    fig = px.line(df, x='date', y=['documents_processed', 'ocr_used'],
                  title='Document Processing Trend',
                  labels={'value': 'Count', 'variable': 'Metric'})
    st.plotly_chart(fig)

    # Document type distribution
    st.subheader("Document Type Distribution")
    doc_types = ['PDF', 'Image', 'Text', 'Word']
    doc_counts = [45, 25, 20, 10]
    fig_pie = px.pie(values=doc_counts, names=doc_types,
                     title='Document Types Processed')
    st.plotly_chart(fig_pie)
