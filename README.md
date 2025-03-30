# Web Crawler & Image Extractor

A comprehensive web crawling tool with image extraction capabilities and keyword-based content filtering. Built with Streamlit and the crawl4ai library, this application efficiently crawls websites, extracts relevant content and images based on keywords, and presents the results in an interactive web interface.

## Features

- **Interactive Web UI**: User-friendly Streamlit interface for configuring and running crawls
- **Keyword-Based Filtering**: Extract only content relevant to specified keywords
- **Real-Time Progress Tracking**: Live updates during the crawling process
- **Image Extraction**: Automatically download and categorize images from websites
- **Content Analysis**: Analyze keyword frequency and relevance across pages
- **Highlighted Content**: View extracted content with keyword highlights
- **Result Organization**: Structured storage of crawl results for easy access

## Installation

### Prerequisites

- Python 3.8+
- pip package manager
- chromium browser

### Setup without Docker

1. Clone the repository:
```bash
git clone https://github.com/lahiruramesh/web-snapper.git
cd web-snapper
```

2. Create and activate virtual environment
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install required packages
```bash
pip install -r requirements.txt
```

4. Starting the application
```bash
streamlit run main.py
```

### Setup with Docker
```bash
docker build -t web-snapper .
```
```bash
docker run -p 8501:8501 -v $(pwd)/crawler_results:/app/crawler_results web-snapper
```



The application will open in your default web browser at http://localhost:8501

