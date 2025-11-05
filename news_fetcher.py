import os
from googleapiclient.discovery import build

# --- CONFIGURATION ---

# This is the Custom Search Engine ID (CX) for news fetching
GOOGLE_SEARCH_CX = 'a03cba227032b4566'

# The full list of 50 domains compiled previously for targeted searching
NEWS_DOMAINS = [
    "site:wsj.com",
    "site:bloomberg.com",
    "site:reuters.com",
    "site:ft.com",
    "site:cnbc.com",
    "site:marketwatch.com",
    "site:investing.com",
    "site:thestreet.com",
    "site:barrons.com",
    "site:forbes.com",
    "site:businessinsider.com",
    "site:economist.com",
    "site:kiplinger.com",
    "site:fortune.com",
    "site:usatoday.com/money",
    "site:apnews.com/business",
    "site:npr.org/sections/money",
    "site:bizjournals.com",
    "site:yale.edu/som/news",
    "site:seekingalpha.com",
    "site:fool.com",
    "site:investopedia.com",
    "site:morningstar.com",
    "site:zacks.com",
    "site:schwab.com/resource/insights",
    "site:fidelity.com/insights",
    "site:etftrends.com",
    "site:tradingeconomics.com",
    "site:dlacalle.com",
    "site:nasdaq.com",
    "site:nyse.com",
    "site:cboe.com",
    "site:cmegroup.com",
    "site:lse.co.uk",
    "site:sgx.com",
    "site:afr.com",
    "site:smh.com.au/business",
    "site:abc.net.au/news/business",
    "site:theage.com.au/business",
    "site:theaustralian.com.au/business",
    "site:finance.yahoo.com",
    "site:google.com/finance",
    "site:moneymorning.com",
    "site:thisismoney.co.uk",
    "site:investorplace.com",
    "site:benzinga.com",
    "site:fxstreet.com",
    "site:forexlive.com",
    "site:marketbeat.com",
]


def fetch_news_sentiment(query="global economic risk, market outlook, inflation forecast"):
    """
    Fetches relevant news articles using the Google Custom Search JSON API 
    and formats them into a structured string for the Gemini analysis model.
    """
    try:
        # 1. Securely retrieve the API Key from the environment
        API_KEY = os.environ.get("GOOGLE_SEARCH_API_KEY")
        if not API_KEY:
            print("Error: GOOGLE_SEARCH_API_KEY environment variable not found. Skipping news fetch.")
            return "News fetching failed: API key missing."
        
        # 2. Build the Google Custom Search service client
        service = build("customsearch", "v1", developerKey=API_KEY)
        
        # 3. Construct the targeted query
        domain_filter = " OR ".join(NEWS_DOMAINS)
        full_query = f'({query}) {domain_filter}'
        
        print(f"Executing Google Search API query to retrieve articles...")
        
        # 4. Execute the search and fetch 10 high-quality results
        res = service.cse().list(
            q=full_query,
            cx=GOOGLE_SEARCH_CX,
            num=10  
        ).execute()
        
        articles = res.get('items', [])
        
        if not articles:
            print("Warning: Search successful, but no relevant articles found.")
            return "News fetching successful, but no relevant articles found."
            
        # 5. Format articles into a structured string for the Gemini model
        formatted_news = []
        for i, item in enumerate(articles):
            title = item.get('title', 'No Title')
            snippet = item.get('snippet', 'No Snippet')
            source = item.get('displayLink', 'Unknown Source')
            
            # The model needs clear structure, hence the labels and separators
            formatted_news.append(
                f"Article {i+1} (Source: {source}):\nTitle: {title}\nSnippet: {snippet}\n"
            )
            
        print(f"Success: Retrieved {len(articles)} news articles for analysis.")
        return "\n---\n".join(formatted_news)

    except Exception as e:
        print(f"FATAL Error fetching news sentiment: {e}")
        return f"News fetching failed due to API exception: {e}"