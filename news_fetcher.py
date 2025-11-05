import requests
import os

# Google Custom Search API documentation suggests up to 10 results per query
NUM_ARTICLES = 5

def fetch_news_articles(query_base):
    """
    Fetches news articles using the Google Custom Search API.
    The API Key and CX ID must be set as environment variables.
    """
    
    # --- SECURELY RETRIEVE KEYS ---
    # These must match the names set in your GitHub Secrets exactly.
    API_KEY = os.environ.get("GOOGLE_SEARCH_API_KEY")
    CX_ID = os.environ.get("GOOGLE_SEARCH_CX")

    if not API_KEY or not CX_ID:
        print("Warning: Google Search API keys not found in environment. Skipping news fetch.")
        return []

    # Construct the search query to focus on finance/risk news
    # The `news_fetcher.py` logic handles the full query string
    search_query = f"{query_base} stock market finance risk"
    
    # 1. Base URL for Google Custom Search
    url = "https://www.googleapis.com/customsearch/v1"

    # 2. Parameters for the API call
    params = {
        "key": API_KEY,
        "cx": CX_ID,
        "q": search_query,
        "searchType": "image",  # Requesting image data helps get thumbnails
        "num": NUM_ARTICLES,
        "dateRestrict": "w1", # Restrict to the last week
        "sort": "date", # Sort by date descending
    }

    try:
        response = requests.get(url, params=params)
        response.raise_for_status()  # Raise an exception for bad status codes (4xx or 5xx)
        data = response.json()
        
        articles = []

        # The 'items' list contains the search results
        if 'items' in data:
            for item in data['items']:
                article = {
                    "title": item.get("title", "No Title"),
                    "link": item.get("link", "#"),
                    "snippet": item.get("snippet", "No description available."),
                    "source": item.get("displayLink", "Unknown Source"),
                    "thumbnail_url": None  # Default to None
                }
                
                # Extract the thumbnail from the image section
                if 'pagemap' in item and 'cse_thumbnail' in item['pagemap']:
                    # The first thumbnail is usually the best bet
                    thumbnail_data = item['pagemap']['cse_thumbnail'][0]
                    article["thumbnail_url"] = thumbnail_data.get("src")
                    
                articles.append(article)
                
        return articles

    except requests.exceptions.RequestException as e:
        print(f"Error fetching news articles: {e}")
        return []
    except Exception as e:
        print(f"An unexpected error occurred during news fetch: {e}")
        return []

if __name__ == '__main__':
    # Simple test case:
    print("Running local test fetch...")
    test_articles = fetch_news_articles("US Recession risk")
    print(f"Test found {len(test_articles)} articles.")
    if test_articles:
        print(f"First article title: {test_articles[0]['title']}")
        