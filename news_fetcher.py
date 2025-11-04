# news_fetcher.py

import os
import requests
from typing import List, Dict, Any

# --- CONFIGURATION (remains the same) ---
GOOGLE_SEARCH_API_KEY = os.getenv("GOOGLE_SEARCH_API_KEY")
GOOGLE_SEARCH_CX = os.getenv("GOOGLE_SEARCH_CX") 
GOOGLE_SEARCH_ENDPOINT = "https://www.googleapis.com/customsearch/v1"

def fetch_news_articles(query_topics: str, num_articles: int = 5) -> List[Dict[str, Any]]:
    """
    Fetches relevant news articles, including the URL and thumbnail image.
    """
    if not GOOGLE_SEARCH_API_KEY or not GOOGLE_SEARCH_CX:
        print("Warning: Google Search API keys not found in environment. Skipping news fetch.")
        return []

    search_query = f"{query_topics} news financial market"

    params = {
        'key': GOOGLE_SEARCH_API_KEY,
        'cx': GOOGLE_SEARCH_CX,
        'q': search_query,
        'num': num_articles,
        'sort': 'date',
        'dateRestrict': 'd7'
    }

    try:
        response = requests.get(GOOGLE_SEARCH_ENDPOINT, params=params, timeout=10)
        response.raise_for_status()
        results = response.json()
        
        articles = []
        if 'items' in results:
            for item in results['items']:
                
                # --- NEW LOGIC: Extract the thumbnail URL ---
                image_url = None
                if 'pagemap' in item and 'cse_thumbnail' in item['pagemap']:
                    # The first item in the cse_thumbnail array usually contains the required URL
                    image_url = item['pagemap']['cse_thumbnail'][0].get('src')
                # --- END NEW LOGIC ---

                articles.append({
                    'title': item.get('title'),
                    'link': item.get('link'),
                    'snippet': item.get('snippet'),
                    'thumbnail_url': image_url  # <-- NEW FIELD ADDED
                })
        return articles
        
    except requests.exceptions.RequestException as e:
        print(f"Error fetching Google Search results: {e}")
        return []