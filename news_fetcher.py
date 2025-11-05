import os
from googleapiclient.discovery import build
import time # Included for robustness, although backoff is usually manual with googleapiclient

# --- CONFIGURATION ---

# This is the Custom Search Engine ID (CX) for news fetching
GOOGLE_SEARCH_CX = 'a03cba227032b4566'

# The full list of 50 domains compiled previously for targeted searching
NEWS_DOMAINS = [
    "site:wsj.com", "site:bloomberg.com", "site:reuters.com", "site:ft.com", "site:cnbc.com", 
    "site:marketwatch.com", "site:investing.com", "site:thestreet.com", "site:barrons.com", 
    "site:forbes.com", "site:businessinsider.com", "site:economist.com", "site:kiplinger.com", 
    "site:fortune.com", "site:usatoday.com/money", "site:apnews.com/business", 
    "site:npr.org/sections/money", "site:bizjournals.com", "site:yale.edu/som/news", 
    "site:seekingalpha.com", "site:fool.com", "site:investopedia.com", "site:morningstar.com", 
    "site:zacks.com", "site:schwab.com/resource/insights", "site:fidelity.com/insights", 
    "site:etftrends.com", "site:tradingeconomics.com", "site:dlacalle.com", "site:nasdaq.com", 
    "site:nyse.com", "site:cboe.com", "site:cmegroup.com", "site:lse.co.uk", "site:sgx.com", 
    "site:afr.com", "site:smh.com.au/business", "site:abc.net.au/news/business", 
    "site:theage.com.au/business", "site:theaustralian.com.au/business", "site:finance.yahoo.com", 
    "site:google.com/finance", "site:moneymorning.com", "site:thisismoney.co.uk", 
    "site:investorplace.com", "site:benzinga.com", "site:fxstreet.com", "site:forexlive.com", 
    "site:marketbeat.com",
]


def fetch_news_sentiment(query="global economic risk, market outlook, inflation forecast"):
    """
    Fetches relevant news articles using the Google Custom Search JSON API 
    and formats them into a numbered list of markdown links, as required by the main script.
    """
    try:
        # 1. Securely retrieve the API Key from the environment
        API_KEY = os.environ.get("GOOGLE_SEARCH_API_KEY")
        if not API_KEY:
            print("Error: GOOGLE_SEARCH_API_KEY environment variable not found. Skipping news fetch.")
            return "News fetching failed: API key missing."
        
        # 2. Build the Google Custom Search service client
        # NOTE: This requires google-api-python-client to be installed (pip install google-api-python-client)
        service = build("customsearch", "v1", developerKey=API_KEY)
        
        # 3. Construct the targeted query
        domain_filter = " OR ".join(NEWS_DOMAINS)
        full_query = f'({query}) {domain_filter}'
        
        print(f"Executing Google Search API query to retrieve articles...")
        
        # 4. Execute the search and fetch 10 high-quality results
        res = service.cse().list(
            q=full_query,
            cx=GOOGLE_SEARCH_CX,
            num=10,
            sort='date' # Sort by date to get most recent articles
        ).execute()
        
        articles = res.get('items', [])
        
        if not articles:
            print("Warning: Search successful, but no relevant articles found.")
            return "News fetching successful, but no relevant articles found."
            
        # 5. Format articles into a structured string of **markdown links** for the Gemini model
        formatted_news = []
        for i, item in enumerate(articles):
            title = item.get('title', 'No Title')
            link = item.get('link', '#')

            # Defensive Cleanup: Escape any curly braces { and } which could break
            # downstream Python f-string or .format() calls (which caused the 'f' error).
            # Also clean up internal markdown brackets for consistency.
            safe_title = title.replace('{', '{{').replace('}', '}}').replace('[', '(').replace(']', ')')
            
            # Format as: 1. [Title](Link)
            formatted_news.append(f"{i+1}. [{safe_title}]({link})")
            
        print(f"Success: Retrieved {len(articles)} news articles for analysis.")
        return "\n".join(formatted_news)

    except Exception as e:
        print(f"FATAL Error fetching news sentiment: {e}")
        return f"News fetching failed due to API exception: {e}"

if __name__ == "__main__":
    # Example usage for testing purposes
    print("Running news_fetcher test...")
    test_query = "US inflation and global recession risk 2025"
    news_output = fetch_news_sentiment(test_query)
    print("\n--- Fetched News Context (Raw) ---")
    print(news_output)
