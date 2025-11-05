import json
import datetime
import random 
import requests
import os 
import pandas as pd 
from fredapi import Fred 
import yfinance as yf
from google import genai 
from google.genai import types
from news_fetcher import fetch_news_articles

# --- CONFIGURATION ---

# 1. Output File Path (Must match your front-end fetch)
OUTPUT_FILE = "data/atlas-latest.json" 
# NEW: Archive File Path for infinite scroll
ARCHIVE_FILE = "data/atlas-archive.json" 

# 2. API Keys and Constants (All API keys now read securely from environment)

# Initialize FRED client
FRED_API_KEY = os.environ.get("FRED_API_KEY")
if FRED_API_KEY:
    fred = Fred(api_key=FRED_API_KEY)
else:
    fred = None 
    print("Warning: FRED_API_KEY is missing. FRED-based indicators will return fallbacks.")


# FRED Series IDs (These are NOT secrets and must be defined as constants)
FRED_3YR_ID = "DGS3"
FRED_30YR_ID = "DGS30"
FRED_10YR_ID = "DGS10"  
FRED_HYOAS_ID = "BAMLH0A0HYM2" 
FRED_SOFR_3M_ID = "TB3MS"      
FRED_EFFR_ID = "EFFR"             
FRED_WALCL_ID = "WALCL"           
FRED_WTREGEN_ID = "WTREGEN"      
FRED_RRPONTSYD_ID = "RRPONTSYD"   
FRED_BANK_CDS_ID = "AAA" 
FRED_CONSUMER_DELINQ_ID = "DRCCLACBS" 
FRED_SNAP_ID = "TRP6001A027NBEA" 

# Note: All API-calling functions (e.g., for Polygon.io, Gemini, Alpha Vantage) 
# must also be updated to retrieve their keys directly via os.environ.get() 
# (e.g., os.environ.get("PUT_CALL_API_KEY"), os.environ.get("GEMINI_API_KEY")).
# If they are not updated, the script will now fail when those keys are required.

# --- NEW INDICATOR FUNCTIONS (Treasury Liquidity, Margin Debt, SOFR/OIS) ---

def get_treasury_net_liquidity():
    """
    Calculates Treasury Net Liquidity using FRED data (TGA + Reverse Repo - Fed Balance Sheet).
    Updated to use the global 'fred' client and secure constants.
    """
    if not fred:
        print("FRED client not initialized. Cannot calculate Net Liquidity.")
        return 100.0

    try:
        # Use the secure global FRED constants
        walcl = fred.get_series_latest_release(FRED_WALCL_ID).iloc[-1].item()
        wtregen = fred.get_series_latest_release(FRED_WTREGEN_ID).iloc[-1].item()
        rrpontsyd = fred.get_series_latest_release(FRED_RRPONTSYD_ID).iloc[-1].item()
        
        # Calculation
        # The exact calculation can vary, but generally uses these three series
        net_liquidity = (float(wtregen) + float(rrpontsyd)) - float(walcl)

        print(f"Success: Calculated TREASURY_LIQUIDITY ({net_liquidity:.2f}) from FRED data.")
        return net_liquidity
    except Exception as e:
        print(f"FRED API Error for Net Liquidity: {e}. Returning fallback 100.0.")
        return 100.0


def get_finra_margin_debt_yoy():
    """
    Fetches FINRA Margin Debt (Debit Balances) and calculates YOY change.
    Data is sourced from the official monthly FINRA Excel file.
    Returns: YOY percentage change (e.g., -5.25 for a 5.25% decrease)
    """
    FINRA_URL = "https://www.finra.org/sites/default/files/2021-03/margin-statistics.xlsx"

    try:
        # Requires 'openpyxl' to read .xlsx
        df = pd.read_excel(FINRA_URL, sheet_name=0, header=1)
        df.columns = ['Date', 'Debit_Balance', 'Free_Credit_Cash', 'Free_Credit_Margin']
        df['Date'] = pd.to_datetime(df['Date'], format='%Y-%m', errors='coerce')
        df = df.dropna(subset=['Date', 'Debit_Balance'])
        df = df.sort_values(by='Date', ascending=False).reset_index(drop=True)

        if len(df) < 13:
            print("Not enough historical data for YOY Margin Debt calculation.")
            return 0.0

        current_debt = df['Debit_Balance'][0]
        previous_year_debt = df['Debit_Balance'][12]
        
        yoy_change = ((current_debt / previous_year_debt) - 1) * 100
        
        return round(yoy_change, 2)

    except Exception as e:
        print(f"FINRA Margin Debt Error: {e}")
        return 0.0 # Fallback value


def get_sofr_ois_spread():
    """
    Calculates the SOFR OIS Spread using two FRED series: TB3MS (3-Month Treasury Bill) 
    and EFFR (Effective Federal Funds Rate) or a proxy.
    """
    if not fred:
        print("FRED client not initialized. Cannot calculate SOFR OIS Spread.")
        return 25.0 # Fallback
    
    try:
        # Assuming you use TB3MS as a proxy for the OIS rate or have a custom logic
        # Here, we'll use TB3MS (3-Month Treasury Bill) and EFFR (Effective Federal Funds Rate)
        tb3ms = fred.get_series_latest_release(FRED_SOFR_3M_ID).iloc[-1].item()
        effr = fred.get_series_latest_release(FRED_EFFR_ID).iloc[-1].item()
        
        # Calculate the spread (using percentage difference or basis points conversion if needed)
        spread_bps = (float(tb3ms) - float(effr)) * 100 
        
        print(f"Success: Calculated SOFR_OIS_SPREAD ({spread_bps:.2f} bps) from FRED data.")
        return spread_bps
    except Exception as e:
        print(f"FRED API Error for SOFR OIS Spread: {e}. Returning fallback 25.0.")
        return 25.0


# --- NEW FUNCTION: AI Commentary Generator ---
def generate_ai_commentary(data_dict):
    """
    Generates the 1-2 paragraph AI Analyst Commentary based on data_dict.
    The function securely retrieves the API key from the environment.
    """
    # 1. SECURELY RETRIEVE KEY
    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
    if not GEMINI_API_KEY:
        print("Warning: GEMINI_API_KEY not found in environment. Skipping AI commentary.")
        return None

    # 2. Initialize the client using the retrieved key
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
    except Exception as e:
        print(f"Error initializing Gemini client: {e}. Check your GEMINI_API_KEY.")
        return None

    # 3. Prepare the Prompt with all the data
    data_context = json.dumps(data_dict, indent=2)

    system_instruction = (
        "You are a sophisticated financial analyst named 'Atlas'. "
        "Your task is to synthesize the provided Atlas Dashboard data (JSON format) "
        "into a compelling, 1-2 paragraph commentary for a disciplined investor. "
        "Focus on interpreting the current risk and sentiment score, and providing a clear, "
        "actionable conclusion based on the key indicators."
    )

    prompt = (
        f"Analyze the following data to generate a 1-2 paragraph commentary:\n\n"
        f"--- DASHBOARD DATA ---\n{data_context}\n--- END DATA ---"
    )

    # 4. Configure the API Call
    config = types.GenerateContentConfig(
        system_instruction=system_instruction,
        temperature=0.3, # Lower temperature for factual, consistent output
    )

    # 5. Call the Gemini API
    try:
        print("Starting Gemini API call to generate commentary...")
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=config,
        )
        print("Commentary generated successfully.")
        return response.text
    except Exception as e:
        print(f"Gemini API Error: {e}")
        return None
    

# --- 1. DATA FETCHING AND PARSING FUNCTIONS (UPDATED FOR FALLBACK) ---

# --- 1. DATA FETCHING AND PARSING FUNCTIONS (UPDATED FOR SECURE GLOBAL FRED) ---

def _fetch_fred_data_two_points(series_id):
    """
    Helper function to fetch the two most recent data points for a FRED series,
    using the securely initialized global 'fred' object.
    """
    fallback = [0.0, 0.0]
    
    # Use the global fred object, which is checked for initialization at the top of the script
    if not fred:
        print(f"FRED client not initialized. Returning fallback for {series_id}.")
        return fallback

    try:
        # Fetch the last 2 observations
        # Using get_series_latest_release for maximum data freshness
        data = fred.get_series_latest_release(series_id).iloc[-2:]
        
        if len(data) == 2:
            return [float(data.iloc[0]), float(data.iloc[1])]
        else:
            print(f"FRED Warning: Expected 2 data points for {series_id}, got {len(data)}. Returning fallback.")
            return fallback
            
    except Exception as e:
        print(f"FRED Error fetching 2-point data for {series_id}: {e}. Returning fallback.")
        return fallback
    
def fetch_fx_data(ticker):
    """Fetches the latest data for an FX pair or commodity using yfinance."""
    try:
        # Fetch the data for the given ticker (e.g., 'EURUSD=X', 'CL=F')
        data = yf.download(ticker, period='1d', interval='1d', progress=False)
        if not data.empty:
            value = data['Close'].iloc[-1].item()
            print(f"Success: Fetched {ticker} ({value:.4f}) from yfinance.")
            return value
        print(f"Warning: {ticker} data is empty. Returning fallback.")
        return 0.0 # Generic fallback
    except Exception as e:
        print(f"Error fetching {ticker}: {e}. Returning fallback.")
        return 0.0 # Generic fallback

def calculate_small_large_ratio():
    """
    Calculates the Small-Cap to Large-Cap ratio (e.g., Russell 2000 / S&P 500) using yfinance.
    """
    try:
        # Fetch data for Russell 2000 (^RUT) and S&P 500 (^GSPC)
        tickers = ['^RUT', '^GSPC']
        data = yf.download(tickers, period='1d', interval='1d', progress=False)
        
        if data.empty or len(data.columns) < 2:
            print("Warning: Small/Large Cap ratio data is incomplete. Returning fallback.")
            return 0.42 # Fallback
            
        # Ensure we have the latest closing prices and convert to float
        small_cap = data['Close']['^RUT'].iloc[-1].item()
        large_cap = data['Close']['^GSPC'].iloc[-1].item()
        
        ratio = small_cap / large_cap
        
        print(f"Success: Calculated SMALL_LARGE_RATIO ({ratio:.4f}) from yfinance.")
        return ratio
    except Exception as e:
        print(f"Error calculating Small/Large Cap ratio: {e}. Returning fallback.")
        return 0.42 # Fallback
          

def fetch_indicator_data(indicator_id):
    """
    Fetches the latest data for all indicators, routing to the correct secure function.
    """
    
    # Define a safe fallback value for FRED series 
    FRED_FALLBACK_VALUE = {
        "3Y_YIELD": 3.50, "30Y_YIELD": 4.25, "10Y_YIELD": 4.30, "HY_OAS": 380.0,
        "TREASURY_LIQUIDITY": 100.0,
        "SOFR_OIS": 25.0,
        "BANK_CDS": 85.0,
        "CONSUMER_DELINQUENCIES": 2.2, 
    }

    # ----------------------------------------------------------------------
    # --- FRED API CALLS (Using the global 'fred' client object) ---
    # ----------------------------------------------------------------------
    
    # Map internal IDs to the global FRED constant names
    fred_series_map = {
        "3Y_YIELD": FRED_3YR_ID, 
        "30Y_YIELD": FRED_30YR_ID,
        "10Y_YIELD": FRED_10YR_ID, 
        "HY_OAS": FRED_HYOAS_ID,
        "BANK_CDS": FRED_BANK_CDS_ID, 
        "CONSUMER_DELINQUENCIES": FRED_CONSUMER_DELINQ_ID, 
    }

    
    if indicator_id in fred_series_map:
        series_id = fred_series_map[indicator_id]
        fallback = FRED_FALLBACK_VALUE.get(indicator_id, 0.0)
        
        if fred: # Check if the global fred client was initialized
            try:
                # Get the most recent value from the securely initialized client
                value = fred.get_series_latest_release(series_id).iloc[-1]
                return float(value)
            except Exception as e:
                print(f"FRED Error fetching {indicator_id}: {e}. Returning fallback {fallback}.")
                return fallback
        else:
            print(f"FRED client not initialized. Returning fallback for {indicator_id}.")
            return fallback

    # ----------------------------------------------------------------------
    # --- CUSTOM FRED API CALLS (Multi-Point Fetch) ------------------------
    # ----------------------------------------------------------------------
    
    elif indicator_id == "SNAP_BENEFITS":
        # Calls the corrected helper function, passing only the ID
        return _fetch_fred_data_two_points(FRED_SNAP_ID) 
            
    # ----------------------------------------------------------------------
    # --- LIVE CALCULATED INDICATORS ---------------------------------
    # ----------------------------------------------------------------------
    
    elif indicator_id == "TREASURY_LIQUIDITY":
        return get_treasury_net_liquidity()
    elif indicator_id == "SOFR_OIS": 
        return get_sofr_ois_spread()
    elif indicator_id == "MARGIN_DEBT_YOY": 
        return get_finra_margin_debt_yoy()

  
    # ----------------------------------------------------------------------
    # --- YFINANCE / EXTERNAL API CALLS ------------------------------------
    # ----------------------------------------------------------------------
    
    elif indicator_id == "VIX": 
        return fetch_vix_index() 
    elif indicator_id == "GOLD_PRICE":
        return fetch_gold_price() 
    elif indicator_id == "EURUSD":
        return fetch_fx_data("EURUSD=X") 
    elif indicator_id == "WTI_CRUDE":
        return fetch_fx_data("CL=F") 
    elif indicator_id == "AUDUSD":
        return fetch_fx_data("AUDUSD=X") 
    elif indicator_id == "SPX_INDEX":
        return fetch_spx_index() 
    elif indicator_id == "ASX_200":
        return fetch_asx_200() 
    elif indicator_id == "SMALL_LARGE_RATIO":
        return calculate_small_large_ratio() 

    # Polygon (Calls the new secure function)
    elif indicator_id == "PUT_CALL_RATIO": 
        return fetch_put_call_ratio()
    
    
    # ----------------------------------------------------------------------
    # --- UNIMPLEMENTED PLACEHOLDERS ---------------------------------------
    # ----------------------------------------------------------------------
    elif indicator_id in ["EARNINGS_REVISION", "GEOPOLITICAL", "FISCAL_RISK"]: 
        return "N/A" 
    
    print(f"Warning: No fetch function defined for indicator ID: {indicator_id}")
    return "N/A"


def _fetch_fred_data_two_points(series_id):
    """
    Helper function to fetch the two most recent data points for a FRED series.
    This function has been updated to use the global 'fred' object.
    """
    fallback = [0.0, 0.0]
    
    if not fred:
        print(f"FRED client not initialized. Returning fallback for {series_id}.")
        return fallback

    try:
        # Fetch the last 2 observations
        data = fred.get_series_latest_release(series_id).iloc[-2:]
        if len(data) == 2:
            return [float(data.iloc[0]), float(data.iloc[1])]
        else:
            print(f"FRED Warning: Expected 2 data points for {series_id}, got {len(data)}. Returning fallback.")
            return fallback
            
    except Exception as e:
        print(f"FRED Error fetching 2-point data for {series_id}: {e}. Returning fallback.")
        return fallback

def _fetch_alpha_vantage_quote(symbol, api_key, endpoint):
    """Internal function to fetch a single price quote using Alpha Vantage GLOBAL_QUOTE."""
    params = {
        "function": "GLOBAL_QUOTE",
        "symbol": symbol,
        "apikey": api_key
    }
    
    response = requests.get(endpoint, params=params)
    response.raise_for_status() 
    data = response.json()
    
    if "Error Message" in data:
         raise ValueError(f"API returned error: {data.get('Error Message')}")
    
    global_quote = data.get("Global Quote", {})
    if not global_quote:
        if not data and "Note" in data:
            raise ValueError(f"API note/error: {data.get('Note')}")
         
        raise ValueError("Global Quote data is empty or missing.")

    return float(global_quote.get("05.price"))

def _fetch_yfinance_quote(symbol):
    """Internal function to fetch the latest close price using yfinance."""
    ticker = yf.Ticker(symbol) 
    data = ticker.history(period="1d", interval="1d") 

    if data.empty:
        raise ValueError(f"yfinance returned no data for symbol {symbol}.")

    close_price = data['Close'].iloc[-1]
    
    return float(close_price)

def fetch_put_call_ratio():
    """
    Fetches the Put/Call Ratio (PCCE Ticker) from Polygon.io, securing the key from the environment.
    """
    # 1. SECURELY RETRIEVE KEY and ENDPOINT
    PUT_CALL_API_KEY = os.environ.get("PUT_CALL_API_KEY")
    URL = "https://api.polygon.io/v2/aggs/ticker/PCCE/prev"

    if not PUT_CALL_API_KEY:
        print("Warning: PUT_CALL_API_KEY not found in environment. Using fallback value (0.5).")
        return 0.5 

    params = {
        "apiKey": PUT_CALL_API_KEY,
    }

    try:
        response = requests.get(URL, params=params)
        response.raise_for_status() # Raises an exception for 4xx/5xx status codes
        data = response.json()
        
        results = data.get("results")
        if not results or not isinstance(results, list) or len(results) == 0:
            print("Warning: Polygon.io API returned no results for PCCE. Using fallback.")
            return 0.5

        # The closing price 'c' is the actual ratio value
        ratio_value = results[0].get("c") 

        if ratio_value is None:
             print("Warning: Polygon.io data parsing failed: 'c' (close) price is missing. Using fallback.")
             return 0.5
             
        pcr_value = float(ratio_value)

        # Sanity check: Filter extreme or invalid data points
        if 0.3 <= pcr_value <= 1.5:
            print(f"Success: Fetched PUT_CALL_RATIO ({pcr_value:.2f}) from Polygon.io.")
            return pcr_value
        else:
            print(f"Warning: PUT_CALL_RATIO ({pcr_value:.2f}) is outside normal range (0.3-1.5). Using fallback.")
            return 0.5
        
    except requests.exceptions.RequestException as e:
        print(f"Error fetching PUT_CALL_RATIO from Polygon.io: {e}. Using fallback.")
        return 0.5

def fetch_external_data(endpoint_key, api_key_key, indicator_id, fallback_value):
    """
    Generic function to fetch data from external APIs.
    Routes traffic to yfinance, Polygon, or Alpha Vantage.
    """
    endpoint = API_CONFIG.get(endpoint_key)
    api_key = API_CONFIG.get(api_key_key)

    # 1. PLACEHOLDER CHECK
    if endpoint and endpoint.startswith("YOUR_") or api_key and api_key.startswith("YOUR_"):
        print(f"Placeholder: API endpoint or key for {indicator_id} is not configured. Returning fallback value {fallback_value}.")
        return fallback_value
    
    # --- YFINANCE LOGIC (VIX, Gold, SPX, ASX, SMALL_LARGE_RATIO, WTI_CRUDE, AUDUSD) ---
    
    if indicator_id in ["VIX", "GOLD_PRICE", 
                        "SPX_INDEX", "ASX_200", 
                        "SMALL_LARGE_RATIO", "WTI_CRUDE", "AUDUSD", "EURUSD"]:
        try:
            if indicator_id not in ["SMALL_LARGE_RATIO"]:
                symbol_map = {
                    "VIX": "^VIX",
                    "GOLD_PRICE": "GLD", "SPX_INDEX": "^GSPC",
                    "ASX_200": "^AXJO", "WTI_CRUDE": "USO", "AUDUSD": "AUDUSD=X",
                    "EURUSD": "EURUSD=X"       
                }
                
                symbol = symbol_map[indicator_id]
                value = _fetch_yfinance_quote(symbol)
             
                formatting = "{:.4f}" if indicator_id in ["AUDUSD", "EURUSD"] else "{:.2f}"
                print(f"Success: Fetched {indicator_id} ({formatting.format(value)}) from yfinance.")
     
                return value 
             
            elif indicator_id == "SMALL_LARGE_RATIO":
                small_cap_value = _fetch_yfinance_quote("^RUT") # Russell 2000
                large_cap_value = _fetch_yfinance_quote("^GSPC") # S&P 500
                ratio = small_cap_value / large_cap_value
          
                print(f"Success: Calculated {indicator_id} ({ratio:.4f}) from yfinance data.")
                return ratio 

        except Exception as e:
            print(f"{indicator_id} yfinance Error: Failed to fetch data: {e}. Returning fallback value {fallback_value}.")
            return fallback_value
        
    # --- POLYGON LOGIC (PUT_CALL_RATIO) ---
    
    if indicator_id == "PUT_CALL_RATIO":
        try:
            pcr_value = _fetch_polygon_data(endpoint, api_key)
            
            print(f"Success: Fetched {indicator_id} ({pcr_value:.2f}) from Polygon.io.")
    
            return pcr_value
            
        except Exception as e:
            print(f"{indicator_id} API Error: Data fetch failed: {e}. Returning fallback value {fallback_value}.")
            return fallback_value
            
    # --- ALPHA VANTAGE LOGIC (ONLY EURUSD REMAINS) ---
         
    
    # This section is redundant if EURUSD is handled by YFinance above, but is preserved for completeness.
    if indicator_id in ["EURUSD"]:
        try:
            av_value = _fetch_alpha_vantage_quote("EURUSD", api_key, endpoint)
            formatting = "{:.4f}"
            print(f"Success: Fetched {indicator_id} ({formatting.format(av_value)}) from Alpha Vantage.")
            return av_value 
   
        except Exception as e:
            print(f"{indicator_id} API Error: Data fetch failed: {e}. Returning fallback value {fallback_value}.")
            return fallback_value
            
    # Final Catch-All 
    else:
        print(f"Generic Success: {indicator_id} is correctly routed. Logic not implemented. Returning fallback value {fallback_value}.")
        return fallback_value  

# --- NEW: SOURCE LINK UTILITY ---

def _update_indicator_sources(indicators):
    """Adds correct source links to indicators based on their fetch method."""
    YFINANCE_BASE = "https://finance.yahoo.com/quote/"
    FINRA_LINK = "https://www.finra.org/investors/market-and-financial-data/margin-statistics"
    
    # Map indicator IDs to their YFinance ticker symbols (for source links)
    YFINANCE_SOURCES = {
        "VIX": YFINANCE_BASE + "%5EVIX/", "GOLD_PRICE": YFINANCE_BASE + "GLD/", 
        "SPX_INDEX": YFINANCE_BASE + "%5EGSPC/", "ASX_200": YFINANCE_BASE + "%5EAXJO/",
        "WTI_CRUDE": YFINANCE_BASE + "USO/", "AUDUSD": YFINANCE_BASE + "AUDUSD=X/",
        "SMALL_LARGE_RATIO": YFINANCE_BASE + "%5ERUT/",
    }
   
    # Special case for FRED, Polygon, and Calculated Indicators
    FRED_SOURCES = {
        "3Y_YIELD": "https://fred.stlouisfed.org/series/DGS3",
        "30Y_YIELD": "https://fred.stlouisfed.org/series/DGS30",
        "10Y_YIELD": "https://fred.stlouisfed.org/series/DGS10",
        "HY_OAS": "https://fred.stlouisfed.org/series/BAMLH0A0HYM2",
        "TREASURY_LIQUIDITY": "https://fred.stlouisfed.org/series/WALCL", 
        "SOFR_OIS": "https://fred.stlouisfed.org/series/SOFR3MAD", 
        "SNAP_BENEFITS": "https://fred.stlouisfed.org/series/SNPTA" # Updated FRED ID for SNAP
    }
    
    POLYGON_SOURCES = {
        "PUT_CALL_RATIO": "https://polygon.io/docs/options/get_v2_aggs_ticker__tickervar__prev",
    }
    
    AV_SOURCES = {
        "EURUSD": "https://www.alphavantage.co/documentation/#currency-exchange",
    }
    
    CUSTOM_SOURCES = {
        "MARGIN_DEBT_YOY": FINRA_LINK,
        "FISCAL_RISK": "Composite/Internal Model (VIX, SNAP, CPI)",
        "GEOPOLITICAL": "Manual Input/Qualitative Assessment"
    }

    for indicator in indicators:
        indicator_id = indicator["id"]
     
        if indicator_id in YFINANCE_SOURCES:
            indicator["source_link"] = YFINANCE_SOURCES[indicator_id]
        elif indicator_id in FRED_SOURCES:
            indicator["source_link"] = FRED_SOURCES[indicator_id]
        elif indicator_id in POLYGON_SOURCES:
            indicator["source_link"] = POLYGON_SOURCES[indicator_id]
        elif indicator_id in AV_SOURCES:
            indicator["source_link"] = AV_SOURCES[indicator_id]
        elif indicator_id in CUSTOM_SOURCES:
            indicator["source_link"] = CUSTOM_SOURCES[indicator_id]
        else:
            indicator["source_link"] = indicator.get("source_link", "N/A") 
            
    return indicators

# --- NEW: ARCHIVE LOGIC ---

def save_to_archive(overall_data):
    """
    Saves the new narrative entry to the beginning of the central archive file.
    """
    archive_entry = {
        "date": overall_data["date"],
        "status": overall_data["status"],
        "score": overall_data["score"],
        "comment": overall_data["comment"],
        "daily_narrative": overall_data["daily_narrative"],
    }
    
    archive_list = []
    
    # 1. Load existing archive
    if os.path.exists(ARCHIVE_FILE):
        try:
            with open(ARCHIVE_FILE, 'r') as f:
                archive_list = json.load(f)
        except json.JSONDecodeError:
            print(f"Archive Warning: Could not decode {ARCHIVE_FILE}. Starting new archive.")
            archive_list = []

    # 2. Prepend the new entry (newest first)
    archive_list.insert(0, archive_entry)
    
    # 3. Save the updated list back to the archive file
    try:
        with open(ARCHIVE_FILE, 'w') as f:
            json.dump(archive_list, f, indent=4)
        print(f"Archive Success: Narrative saved to {ARCHIVE_FILE}.")
    except Exception as e:
        print(f"Archive Error: Failed to save archive file: {e}")


# --- UTILITY FUNCTION FOR SCORING OUTPUT ---

def generate_score_output(status, note, action, score, source_link):
    """Formats the output into a dictionary for clean function returns."""
    return {
        "status": status, 
        "note": note, 
        "action": action,
        "score_value": score, 
        "source_link": source_link
    }

# --- 2. RISK SCORING LOGIC (All Functions Combined) ---

def score_vix(value):
    """VIX (US implied vol) Scoring"""
    status = "Green"
    note = f"VIX close at {value:.2f}. Low implied volatility."
    action = "No change."
    score = 0.0
    source_link = "https://finance.yahoo.com/quote/%5EVIX/"

    if value >= 22.0:
        status = "Red"
        note = f"VIX is elevated at {value:.2f}. High market fear."
        score = 2.0  # Positive score for increased risk
        action = "Increase portfolio volatility hedges."
    elif value >= 18.0:
        status = "Amber"
        note = f"VIX is moderate at {value:.2f}. Volatility is starting to increase."
        score = 1.0
        action = "Monitor volatility trends closely."

    return generate_score_output(status, note, action, score, source_link)


def score_3y_yield(value): 
    """US 3-yr Treasury yield Scoring - Measures medium-term rate pressure."""
    status = "Green"
    note = f"Yield at {value:.2f}%. Normal medium-term rate environment."
    action = "No change."
    score = 0.0
    source_link = "https://www.treasury.gov/resource-center/data-chart-center/interest-rates/"

    if value >= 4.50:
        status = "Red"
        note = f"Yield at {value:.2f}%. Aggressive medium-term rate pricing. Significant pressure on duration."
        action = "Aggressively avoid intermediate duration locks."
        score = 1.0
    elif value >= 3.40:
        status = "Amber"
        note = f"Yield at {value:.2f}%. Medium-term rate pressure."
        action = "Avoid intermediate locks; prefer short/floating rate instruments."
        score = 0.5

    return generate_score_output(status, note, action, score, source_link)


def score_10y_yield(value): 
    """US 10-yr Treasury yield Scoring"""
    status = "Green"
    note = f"Yield at {value:.2f}%."
    action = "No change."
    score = 0.0
    source_link = "https://www.treasury.gov/resource-center/data-chart-center/interest-rates/Pages/TextView.aspx?data=yield"

    if value >= 4.75:
        status = "Red"
        note = f"Yield at {value:.2f}%. Above the critical Atlas pivot at 4.75%."
        action = "Aggressively favour short duration."
        score = 1.0
    elif value >= 4.0:
        status = "Amber"
        note = f"Yield at {value:.2f}%. Elevated yields."
        action = "Watch the Atlas pivot at 4.75%; favour short duration."
        score = 0.5

    return generate_score_output(status, note, action, score, source_link)


def score_30y_yield(value): 
    """US 30-yr Treasury yield Scoring - Measures long-term inflation/fiscal risk."""
    status = "Green"
    note = f"Yield at {value:.2f}%. Normal long-term rate environment."
    action = "No change."
    score = 0.0
    source_link = "https://www.treasury.gov/resource-center/data-chart-center/interest-rates/"

    if value >= 5.00:
        status = "Red"
        note = f"Yield at {value:.2f}%. Long-term yields are aggressively priced. Fiscal concerns are dominant."
        action = "Absolutely avoid long duration exposure. Favour cash/short-term duration."
        score = 1.0
    elif value >= 4.00:
        status = "Amber"
        note = f"Yield at {value:.2f}%. Elevated long-term yields reflecting fiscal risk/inflation concerns."
        action = "Watch the 5.0% threshold. Limit long duration locks."
        score = 0.5

    return generate_score_output(status, note, action, score, source_link)


def score_gold_price(value): 
    """Gold Price (GLD ETF Proxy) Scoring"""
    status = "Green"
    note = f"Gold (GLD) is stable at ${value:.2f}. Suggests manageable inflation/risk."
    action = "No change."
    score = 0.0
    source_link = "https://finance.yahoo.com/quote/GLD/"

    if value <= 180.0:
        status = "Red"
        note = f"Gold (GLD) has broken below key support at ${value:.2f}. Suggests persistent disinflation/low risk demand."
        score = 1.5
        action = "Re-assess inflation-hedging exposure."
    elif value <= 190.0:
        status = "Amber"
        note = f"Gold (GLD) is drifting lower at ${value:.2f}. Monitor for risk-off flows."
        score = 0.5
        action = "Monitor for disinflationary pressure."
    elif value >= 210.0:
        status = "Amber"
        note = f"Gold (GLD) is rallying sharply at ${value:.2f}. Indicates rising inflation expectations or systemic risk."
        score = 0.5
        action = "Consider increasing real asset allocation."

    return generate_score_output(status, note, action, score, source_link)


def score_eurusd(value):
    """EUR/USD Exchange Rate Scoring (Proxy for USD strength/global risk sentiment)"""
    status = "Green"
    note = f"EUR/USD is stable at {value:.4f}. Indicates balanced global risk/economic outlook."
    action = "No change."
    score = 0.0
    source_link = "https://www.alphavantage.co/documentation/#currency-exchange"

    if value <= 1.0500:
        status = "Red"
        note = f"EUR/USD is very weak at {value:.4f}. Signals significant USD strength and global 'risk-off' sentiment."
        score = 1.5
        action = "Increase USD cash reserves; reduce emerging market exposure."
    elif value <= 1.1000:
        status = "Amber"
        note = f"EUR/USD is below key support levels at {value:.4f}. Monitor for increasing global liquidity stress."
        score = 0.75
        action = "Monitor USD liquidity closely."
    elif value >= 1.2000:
        status = "Amber"
        note = f"EUR/USD is strong at {value:.4f}. Signals broad USD weakness, which can be inflationary."
        score = 0.5
        action = "Check commodity and inflation-linked bond exposure."

    return generate_score_output(status, note, action, score, source_link)


def score_wti_crude(value):
    """WTI Crude Oil Scoring - Measures global inflation and geopolitical risk."""
    status = "Green"
    note = f"WTI Crude at ${value:.2f}/bbl. Normal price range, favorable for growth."
    action = "No change."
    score = 0.0
    source_link = "https://finance.yahoo.com/quote/USO/"

    if value >= 95.0:
        status = "Red"
        note = f"WTI Crude at ${value:.2f}/bbl. Price indicates strong geopolitical risk or major supply shock."
        score = 1.5
        action = "Increase commodity and inflation hedges."
    elif value >= 85.0:
        status = "Amber"
        note = f"WTI Crude at ${value:.2f}/bbl. Price is elevated; watch for demand destruction or geopolitical escalation."
        score = 0.5
        action = "Monitor inflation expectations closely."
    elif value <= 60.0:
        status = "Amber"
        note = f"WTI Crude at ${value:.2f}/bbl. Low price indicates global slowdown or demand weakness."
        score = 0.5
        action = "Monitor global growth indicators."

    return generate_score_output(status, note, action, score, source_link)


def score_audusd(value):
    """AUD/USD Exchange Rate Scoring - Measures global risk appetite and US Dollar strength."""
    status = "Green"
    note = f"AUDUSD at {value:.4f}. Favorable FX conditions; AUD reflects risk-on sentiment."
    action = "No change."
    score = 0.0
    source_link = "https://www.tradingview.com/symbols/AUDUSD/"

    if value <= 0.6500:
        status = "Red"
        note = f"AUDUSD at {value:.4f}. AUD remains under pressure. Strong risk-off or persistent US Dollar strength."
        action = "Favour US Dollar liquidity over AUD assets; watch commodity prices."
        score = 1.0
    elif value <= 0.7000:
        status = "Amber"
        note = f"AUDUSD at {value:.4f}. AUD is consolidating. Global risk appetite is tentative."
        action = "Monitor closely for breaks below 0.6500."
        score = 0.5

    return generate_score_output(status, note, action, score, source_link)


def score_hy_oas(value): 
    """High Yield Option Adjusted Spread (HY OAS) Scoring - Measures US credit stress."""
    status = "Green"
    note = f"HY OAS at {value:.0f} bps. Tight credit spreads, market calm."
    action = "No change."
    score = 0.0
    source_link = "https://fred.stlouisfed.org/series/BAMLH0A0HYM2"

    if value >= 400.0:
        status = "Red"
        note = f"HY OAS at {value:.0f} bps. Extreme credit spread widening. Signals severe corporate funding stress."
        score = 2.0
        action = "Aggressively reduce corporate credit exposure; favour high-grade government bonds."
    elif value >= 350.0:
        status = "Amber"
        note = f"HY OAS at {value:.0f} bps. Elevated credit stress. Watch for funding difficulties in weaker corporations."
        score = 1.0
        action = "Reduce corporate credit risk; favour investment-grade bonds."

    return generate_score_output(status, note, action, score, source_link)


def score_spx_index(value):
    """S&P 500 Index Scoring - Measures US Equity Risk (Macro Indicator)."""
    status = "Green"
    note = f"S&P 500 Index at {value:,.0f}. Trading near highs, bullish momentum prevailing."
    action = "No change."
    score = 0.0
    source_link = "https://finance.yahoo.com/quote/%5EGSPC"

    # Assume index pivot point for correction is 5000.0
    if value <= 4400.0:
        status = "Red"
        note = f"S&P 500 Index at {value:,.0f}. Aggressive sell-off/Correction >12%. Structural equity risk is high."
        action = "Sell/Hedge significant equity exposure. Wait for VIX confirmation below 22."
        score = 1.0
    elif value <= 4800.0: # Updated threshold to reflect current market (assuming a 5000 pivot)
        status = "Amber"
        note = f"S&P 500 Index at {value:,.0f}. Moderate pullback from highs. Equity risk is elevated."
        action = "Avoid adding new equity exposure. Maintain existing hedges."
        score = 0.5
    
    return generate_score_output(status, note, action, score, source_link)


def score_asx_200(value):
    """S&P/ASX 200 Scoring - Measures Australian Equity Risk and Domestic Sentiment (Micro Indicator)."""
    status = "Green"
    note = f"ASX 200 Index at {value:,.0f}. Trading near highs, bullish sentiment prevailing."
    action = "No change."
    score = 0.0
    source_link = "https://finance.yahoo.com/quote/%5EAXJO"

    if value <= 8300.0:
        status = "Red"
        note = f"ASX 200 Index at {value:,.0f}. Significant sell-off / Correction >10%. Structural equity risk is high, particularly in Financials/Materials."
        action = "Sell/Hedge significant AU equity exposure. Wait for VIX/HY OAS confirmation."
        score = 1.0
    elif value <= 8700.0:
        status = "Amber"
        note = f"ASX 200 Index at {value:,.0f}. Moderate pullback from highs. Equity risk is elevated."
        score = 0.5
        action = "Avoid adding new AU equity exposure."
    
    return generate_score_output(status, note, action, score, source_link)


def score_treasury_liquidity(value): 
    """Treasury Net Liquidity Scoring - Measures system-wide liquidity/risk."""
    # Value is in Billions USD
    status = "Green"
    note = f"Net Liquidity at ${value:.1f}B. Systemic liquidity is robust."
    action = "No change."
    score = 0.0
    source_link = "https://fred.stlouisfed.org/series/WALCL"
    
    # Critical threshold for liquidity stress (inferred from common analyst models)
    if value <= -250.0:
        status = "Red"
        note = f"Net Liquidity at ${value:.1f}B. Deep liquidity deficit. Signals systemic funding stress."
        score = 2.0
        action = "Aggressively increase cash/liquidity reserves; reduce all speculative exposure."
    elif value <= 50.0:
        status = "Amber"
        note = f"Net Liquidity at ${value:.1f}B. Liquidity is tightening. Monitor short-term funding markets closely."
        score = 1.0
        action = "Limit duration exposure; favour short-term liquid assets."
        
    return generate_score_output(status, note, action, score, source_link)


def score_sofr_ois(value):
    """SOFR/OIS Spread Scoring - Measures interbank counterparty risk."""
    status = "Green"
    note = f"SOFR/OIS Spread at {value:.1f} bps. Low implied counterparty risk."
    action = "No change."
    score = 0.0
    source_link = "https://fred.stlouisfed.org/series/SOFR3MAD"

    if isinstance(value, str):
        if value.upper() == 'N/A':
            return generate_score_output("N/A", "Data N/A: SOFR/OIS requires FRED data.", "Cannot score due to missing data.", 0.0, source_link)
        try:
            value = float(value)
        except ValueError:
            return generate_score_output("Error", "Error: Spread value could not be converted to number.", "Cannot score due to data error.", 0.0, "")

    if value >= 40.0:
        status = "Red"
        note = f"SOFR/OIS Spread at {value:.1f} bps. Aggressive widening. Indicates high bank-counterparty risk."
        score = 2.0
        action = "Aggressively reduce counterparty risk exposure; favour collateralized lending."
    elif value >= 25.0:
        status = "Amber"
        note = f"SOFR/OIS Spread at {value:.1f} bps. Elevated widening. Monitor interbank lending stress."
        score = 1.0
        action = "Monitor bank solvency and interbank rates closely."
        
    return generate_score_output(status, note, action, score, source_link)


def score_put_call_ratio(value):
    """Put/Call Ratio Scoring - Measures retail/institutional sentiment."""
    status = "Green"
    note = f"Put/Call Ratio at {value:.2f}. Balanced market sentiment."
    action = "No change."
    score = 0.0
    source_link = "https://polygon.io/docs/options/get_v2_aggs_ticker__tickervar__prev"

    if isinstance(value, str):
        if value.upper() == 'N/A':
            return generate_score_output("N/A", "Data N/A: Put/Call requires Polygon data.", "Cannot score due to missing data.", 0.0, source_link)
        try:
            value = float(value)
        except ValueError:
            return generate_score_output("Error", "Error: Ratio value could not be converted to number.", "Cannot score due to data error.", 0.0, "")

    if value >= 1.20:
        status = "Red"
        note = f"Ratio at {value:.2f}. Extreme bearishness (too many puts). Suggests a potential short-term reversal/capitulation."
        score = 1.0 # Counter-intuitive: extreme fear is bullish
        action = "Watch for a sharp technical rally. Avoid selling at current levels."
    elif value >= 1.0:
        status = "Amber"
        note = f"Ratio at {value:.2f}. Bearish sentiment is elevated. Monitor for a fear-driven market bottom."
        score = 0.5
        action = "Avoid adding new short positions."
    elif value <= 0.8:
        status = "Amber"
        note = f"Ratio at {value:.2f}. Extreme complacency (too many calls). Suggests a short-term top."
        score = 0.5 # Risk is high from complacency
        action = "Reduce speculative long positions."

    return generate_score_output(status, note, action, score, source_link)


def score_margin_debt_yoy(value): 
    """FINRA Margin Debt YOY Scoring - Measures leverage in the equity system."""
    status = "Green"
    note = f"Margin Debt YOY at {value:.1f}%. Leverage is stable/contracting moderately."
    action = "No change."
    score = 0.0
    source_link = "https://www.finra.org/investors/market-and-financial-data/margin-statistics"

    if isinstance(value, str):
        if value.upper() == 'N/A':
            return generate_score_output("N/A", "Data N/A: Margin Debt requires FINRA data.", "Cannot score due to missing data.", 0.0, source_link)
        try:
            value = float(value)
        except ValueError:
            return generate_score_output("Error", "Error: Debt value could not be converted to number.", "Cannot score due to data error.", 0.0, "")

    if value >= 10.0:
        status = "Red"
        note = f"Margin Debt YOY at {value:.1f}%. Leverage is expanding aggressively. High risk of forced liquidation if markets fall."
        score = 1.5
        action = "Aggressively deleverage equity exposure; increase cash."
    elif value >= 5.0:
        status = "Amber"
        note = f"Margin Debt YOY at {value:.1f}%. Leverage is expanding. Monitor for an acceleration."
        score = 0.5
        action = "Monitor broker-lending rates closely."
        
    return generate_score_output(status, note, action, score, source_link)


def score_small_large_ratio(value):
    """Russell 2000 / S&P 500 Ratio Scoring - Measures market breadth and risk appetite."""
    status = "Red" # Default to Red/Worry since small-cap underperformance is the norm in weak markets
    note = f"Ratio at {value:.4f} — small-caps are heavily underperforming. Poor internals."
    action = "Avoid high-risk small-cap exposure."
    score = 1.0
    source_link = "https://finance.yahoo.com/quote/%5ERUT/"

    if isinstance(value, str):
        if value.upper() == 'N/A':
            return generate_score_output("N/A", "Data N/A: Ratio requires YFinance data.", "Cannot score due to missing data.", 0.0, source_link)
        try:
            value = float(value)
        except ValueError:
            return generate_score_output("Error", "Error: Ratio value could not be converted to number.", "Cannot score due to data error.", 0.0, "")

    if isinstance(value, float):
        if value >= 0.45:
            status = "Green"
            note = f"Ratio at {value:.2f} — small-caps outperforming. Healthy internals/market breadth."
            score = 0.0
            action = "Favour cyclical/growth stocks."
        elif value >= 0.42:
            status = "Amber"
            note = f"Ratio at {value:.2f} — small-cap outperformance is fading. Monitor market breadth."
            score = 0.5
            action = "Reduce incremental growth exposure."
    # Default Red status covers the < 0.42 case.
    return generate_score_output(status, note, action, score, source_link)


def score_earnings_revision(value): 
    """Earnings Revision Index Scoring (Placeholder)."""
    # This is a placeholder and should return a default based on the assumption of "N/A"
    return generate_score_output("N/A", "Data N/A: Earnings Revisions not automated.", "No change.", 0.0, "N/A")

def score_bank_cds(value):
    """Bank CDS (Credit Default Swap) Scoring."""
    # Placeholder: Assuming value is a measure in Basis Points (bps)
    status = "Green"
    note = f"Bank CDS at {value:.0f} bps. Low implied banking stress."
    action = "No change."
    score = 0.0
    source_link = "https://fred.stlouisfed.org/series/AAA" # Assuming this is a proxy
    
    # Placeholder Logic
    if value >= 150.0:
        status = "Red"
        note = f"Bank CDS at {value:.0f} bps. Aggressive widening. Signals high counterparty/banking sector stress."
        score = 1.5
        action = "Reduce exposure to regional banks and highly leveraged financial institutions."
    elif value >= 100.0:
        status = "Amber"
        note = f"Bank CDS at {value:.0f} bps. Elevated widening. Caution on unsecured bank exposure."
        score = 0.5
        action = "Monitor banking liquidity and deposits closely."
        
    return generate_score_output(status, note, action, score, source_link)


def score_consumer_delinquencies(value):
    """Consumer Delinquency Rate Scoring (Micro Indicator)."""
    # Placeholder: Assuming value is a percentage rate
    status = "Green"
    note = f"Delinquency Rate at {value:.1f}%. Consumer health is stable."
    action = "No change."
    score = 0.0
    source_link = "https://fred.stlouisfed.org/series/DRCCLACBS" # Assuming this is the source
    
    # Placeholder Logic
    if value >= 3.5:
        status = "Red"
        note = f"Delinquency Rate at {value:.1f}%. Rate is spiking. Signals severe consumer stress."
        score = 2.0
        action = "Aggressively reduce exposure to consumer discretionary and financial stocks with high unsecured loan exposure."
    elif value >= 2.8:
        status = "Amber"
        note = f"Delinquency Rate at {value:.1f}%. Rate is rising. Caution warranted for banks and consumer sectors."
        score = 1.0
        action = "Monitor household debt metrics closely; reduce unsecured credit exposure."
        
    # Default Green status covers the lower range
    return generate_score_output(status, note, action, score, source_link)


def score_geopolitical(value):
    """Geopolitical (China/Russia/region) Scoring (Micro Indicator)."""
    # This is a manual input score (0.0, 0.5, or 1.0)
    manual_score = value
    source_link = "Manual Input/Qualitative Assessment"

    if manual_score == 1.0:
        status = "Red"
        note = "Major escalation flagged (e.g., active conflict / resource shock). Commodity & risk-off shock is imminent."
        action = "Immediate de-risking and full commodity/FX hedge deployment."
        score = 1.0
    elif manual_score == 0.5:
        status = "Amber"
        note = "Tensions elevated (e.g., Ukraine/China/Middle East); still monitor escalation."
        action = "Maintain commodity hedging (e.g., gold/oil) as tactical insurance."
        score = 0.5
    else: # manual_score == 0.0
        status = "Green"
        note = "Tensions stable. No immediate geopolitical shock flagged."
        action = "No change."
        score = 0.0
        
    return generate_score_output(status, note, action, score, source_link)


def score_fiscal_risk(atlas_data):
    """Calculates the FISCAL_RISK score (Max 100) based on four factors."""
    
    # ----------------------------------------------------------------------
    # 1. Social Service Delivery (SNAP Deviation Score) - MAX 25
    # CRITICAL SAFETY CHECK: next() ensures a default list is used if fetch failed.
    # ----------------------------------------------------------------------
    snap_values = next(
        (item['value'] for item in atlas_data['macro'] if item['id'] == 'SNAP_BENEFITS' and isinstance(item['value'], list)), 
        [0.0, 0.0]
    )
    prev_month = snap_values[0]
    curr_month = snap_values[1]
    
    # Calculate MoM % change
    if prev_month > 0:
        snap_mom_change = ((curr_month / prev_month) - 1) * 100
    else:
        snap_mom_change = 0.0
        
    # Scoring: Aggressive SNAP expansion/contraction indicates stress
    if snap_mom_change > 10.0 or snap_mom_change < -10.0:
        snap_score = 25
    elif snap_mom_change > 5.0 or snap_mom_change < -5.0:
        snap_score = 15
    else:
        snap_score = 5 

    # ----------------------------------------------------------------------
    # 2. Public Integrity (Corruption Perception Index - CPI) - MAX 25
    # Placeholder: Using the US score from Transparency International CPI (69)
    # ----------------------------------------------------------------------
    us_cpi = 69
    corruption_score = max(0, min(25, (100 - us_cpi) / 4))

    # ----------------------------------------------------------------------
    # 3. Social Stress Proxy (VIX Index) - MAX 25
    # SAFETY CHECK: Ensures the retrieved value is a number, or default to 0
    # ----------------------------------------------------------------------
    vix_value = next(
        (item['value'] for item in atlas_data['macro'] if item['id'] == 'VIX' and (isinstance(item['value'], (int, float)))), 
        0
    )
    if vix_value > 30:
        civil_unrest_score = 25
    elif vix_value > 20:
        civil_unrest_score = 15
    else:
        civil_unrest_score = 5

    # ----------------------------------------------------------------------
    # 4. Data/Regulatory Confidence (Narrative Analysis Placeholder) - MAX 25
    # ----------------------------------------------------------------------
    reg_confidence_score = 10

    # --- Compile Final Score ---
    total_fiscal_risk_score = (
        snap_score + corruption_score + civil_unrest_score + reg_confidence_score
    )

    # Store the breakdown in the metadata 
    if "meta" not in atlas_data:
        atlas_data["meta"] = {}
    atlas_data["meta"]["fiscal_breakdown"] = {
        "snap_score": snap_score,
        "corruption_score": round(corruption_score, 2),
        "civil_unrest_score": civil_unrest_score,
        "reg_confidence_score": reg_confidence_score
    }
    
    # NOTE: This function returns a float, which is why the main loop failed previously.
    return round(total_fiscal_risk_score, 2)

def fetch_vix_index():
    """Fetches the latest VIX Index value using yfinance."""
    try:
        # Fetch VIX (ticker ^VIX)
        vix_data = yf.download('^VIX', period='1d', interval='1d', progress=False)
        if not vix_data.empty:
            # FIX: Use .item() to extract the single float value from the Pandas Series
            vix_value = vix_data['Close'].iloc[-1].item()
            print(f"Success: Fetched VIX ({vix_value:.2f}) from yfinance.")
            return vix_value
        print("Warning: VIX data is empty. Returning fallback.")
        return 22.0 # Fallback
    except Exception as e:
        print(f"Error fetching VIX: {e}. Returning fallback.")
        return 22.0 # Fallback

def fetch_gold_price():
    """Fetches the latest Gold Price (via GLD ETF) using yfinance."""
    try:
        # Ticker for Gold ETF
        gold_data = yf.download('GLD', period='1d', interval='1d', progress=False)
        if not gold_data.empty:
            # FIX: Use .item() to extract the single float value from the Pandas Series
            gold_value = gold_data['Close'].iloc[-1].item()
            print(f"Success: Fetched GOLD_PRICE ({gold_value:.2f}) from yfinance.")
            return gold_value
        print("Warning: Gold price data is empty. Returning fallback.")
        return 2000.00 # Fallback
    except Exception as e:
        print(f"Error fetching Gold Price: {e}. Returning fallback.")
        return 2000.00 # Fallback
    
def fetch_spx_index():
    """Fetches the latest S&P 500 Index value using yfinance."""
    try:
        # Fetch S&P 500 (ticker ^GSPC)
        spx_data = yf.download('^GSPC', period='1d', interval='1d', progress=False)
        if not spx_data.empty:
            spx_value = spx_data['Close'].iloc[-1].item()
            print(f"Success: Fetched SPX_INDEX ({spx_value:.2f}) from yfinance.")
            return spx_value
        print("Warning: SPX data is empty. Returning fallback.")
        return 4400.0 # Fallback
    except Exception as e:
        print(f"Error fetching SPX: {e}. Returning fallback.")
        return 4400.0 # Fallback

def fetch_asx_200():
    """Fetches the latest S&P/ASX 200 Index value using yfinance."""
    try:
        # Fetch ASX 200 (ticker ^AXJO is commonly used for the index)
        asx_data = yf.download('^AXJO', period='1d', interval='1d', progress=False)
        if not asx_data.empty:
            asx_value = asx_data['Close'].iloc[-1].item()
            print(f"Success: Fetched ASX_200 ({asx_value:.2f}) from yfinance.")
            return asx_value
        print("Warning: ASX 200 data is empty. Returning fallback.")
        return 7000.0 # Fallback
    except Exception as e:
        print(f"Error fetching ASX 200: {e}. Returning fallback.")
        return 7000.0 # Fallback
    

# --- DICTIONARY MAPPING INDICATOR ID TO SCORING FUNCTION (NEW CORRECT LOCATION) ---
SCORING_FUNCTIONS = {
    # MACRO Indicators
    "VIX": score_vix,
    "GOLD_PRICE": score_gold_price,
    "EURUSD": score_eurusd,
    "WTI_CRUDE": score_wti_crude,
    "AUDUSD": score_audusd,
    "3Y_YIELD": score_3y_yield,
    "30Y_YIELD": score_30y_yield,
    "10Y_YIELD": score_10y_yield,
    "HY_OAS": score_hy_oas,
    "TREASURY_LIQUIDITY": score_treasury_liquidity,
    
    # MICRO Indicators
    "SPX_INDEX": score_spx_index,
    "ASX_200": score_asx_200,
    "SOFR_OIS": score_sofr_ois,
    "PUT_CALL_RATIO": score_put_call_ratio,
    "MARGIN_DEBT_YOY": score_margin_debt_yoy,
    "SMALL_LARGE_RATIO": score_small_large_ratio,
    "EARNINGS_REVISION": score_earnings_revision, # Placeholder
    "BANK_CDS": score_bank_cds,
    "CONSUMER_DELINQUENCIES": score_consumer_delinquencies,
    "GEOPOLITICAL": score_geopolitical, # Manual Input/Scored separately
    # SNAP_BENEFITS and FISCAL_RISK are handled internally/composite
}

def _compile_escalation_watch(atlas_data):
    """Compiles a list of indicators that are currently at Amber or Red thresholds."""
    
    # Define a list of indicators and their low/high risk thresholds for the summary
    WATCH_THRESHOLDS = {
        "VIX": {"name": "VIX Index", "threshold": 18.0, "threshold_desc": "Above 18"},
        "10Y_YIELD": {"name": "10yr Yield", "threshold": 4.0, "threshold_desc": "Above 4.0%"},
        "HY_OAS": {"name": "HY OAS", "threshold": 350.0, "threshold_desc": "Above 350 bps"},
        "SOFR_OIS": {"name": "SOFR/OIS Spread", "threshold": 25.0, "threshold_desc": "Above 25 bps"},
        "EURUSD": {"name": "EUR/USD", "threshold": 1.1000, "threshold_desc": "Below 1.10"},
        "TREASURY_LIQUIDITY": {"name": "Net Liquidity", "threshold": 50.0, "threshold_desc": "Below $50B"},
    }
    
    all_indicators = atlas_data['macro'] + atlas_data['micro']
    escalation_list = []
    
    for watch_id, watch_info in WATCH_THRESHOLDS.items():
        indicator = next((item for item in all_indicators if item['id'] == watch_id), None)
        if not indicator:
            continue
            
        current_value = indicator.get("value")
        is_breached = False
        
        # Determine breach logic (Low is bad for EURUSD/Liquidity, High is bad for VIX/Yields/Spreads)
        if watch_id in ["EURUSD", "TREASURY_LIQUIDITY"] and isinstance(current_value, (int, float)) and current_value <= watch_info["threshold"]:
            is_breached = True # Low is bad
        elif watch_id in ["HY_OAS", "SOFR_OIS", "VIX", "10Y_YIELD"] and isinstance(current_value, (int, float)) and current_value >= watch_info["threshold"]:
            is_breached = True # High is bad

        if is_breached:
            # Format the current reading appropriately
            if isinstance(current_value, (int, float)):
                if watch_id in ["HY_OAS", "BANK_CDS"]:
                    formatted_value = f"{current_value:.0f}"
                elif watch_id in ["SOFR_OIS", "VIX"]:
                    formatted_value = f"{current_value:.1f}"
                else:
                    formatted_value = str(current_value)
            else:
                formatted_value = "N/A"
                
            escalation_list.append({
                "name": watch_info["name"],
                "current_reading": formatted_value,
                "alarm_threshold": watch_info["threshold_desc"]
            })
            
    return escalation_list


def score_atlas_commentary(atlas_data):
    """ Uses the Gemini API to generate structured commentary based on the scored data. """
    
    # This function is now deprecated in favor of the simpler generate_ai_commentary
    # but the logic for generating the summary is useful for prompting.
    
    # Format the current indicator data for the prompt
    indicator_summary = "\n".join([
        f"{ind['name']}: Value={ind['value']:.2f}, Status={ind['status']}, Score={ind['score_value']:.1f}" 
        for ind in atlas_data["macro"] + atlas_data["micro"] 
        if ind['id'] != 'SNAP_BENEFITS' # Exclude SNAP as it's an input for FISCAL_RISK
    ])

    # Use keys from the 'overall' block for the prompt
    current_score = atlas_data['overall'].get('score', 0.0)
    current_status = atlas_data['overall'].get('status', 'MONITOR')
    
    prompt = (
        f"Based on the following Atlas Risk Dashboard data, generate a daily analysis.\n\n"
        f"- **Current Atlas Score:** {current_score:.1f} ({current_status})\n"
        f"- **Indicator Summary:**\n{indicator_summary}"
    )

    # Call the simple narrative function
    narrative = generate_ai_commentary(atlas_data)

    # Return a dummy commentary structure (as the main logic uses the single narrative)
    return {
        "Short insight": "AI Commentary is now generated as a single narrative block.",
        "Immediate actions": [],
        "Escalation watch": [],
        "atlas_status_summary": []
    }


# --- 3. MAIN EXECUTION FUNCTION (Reconstructed) ---

MAX_SCORE = 15.0 # Total possible score, estimated.

def run_update_process(atlas_data):
    """
    Orchestrates the scoring, overall status calculation, and commentary generation.
    """
    
    all_indicators = atlas_data["macro"] + atlas_data["micro"]
    composite_score = 0.0

    # 1. SCORING LOOP
    for indicator in all_indicators:
        indicator_id = indicator["id"]
        scoring_func = SCORING_FUNCTIONS.get(indicator_id)
        
        # Skip indicators that are composites or only serve as inputs (like SNAP)
        if indicator_id in ["FISCAL_RISK", "SNAP_BENEFITS"]:
            indicator["score_value"] = 0.0
            continue
        
        if scoring_func:
            value = indicator.get("value")
            result = scoring_func(value)
            
            # Update the indicator dictionary with scoring results
            score_value = result["score_value"]
            indicator["status"] = result["status"]
            indicator["note"] = result["note"]
            indicator["action"] = result["action"]
            indicator["score_value"] = score_value
            
            # Add to composite score
            composite_score += score_value
        else:
            indicator["score_value"] = 0.0

    # 2. CALCULATE AND SCORE FISCAL_RISK (Special Case)
    fiscal_indicator = next((item for item in all_indicators if item["id"] == "FISCAL_RISK"), None)
    if fiscal_indicator:
        fiscal_score = score_fiscal_risk(atlas_data)
        fiscal_indicator["value"] = fiscal_score 
        fiscal_indicator["score_value"] = fiscal_score
        
        # Manually assign status/note based on the score threshold
        if fiscal_score > 75.0:
            fiscal_indicator["status"] = "Red"
            fiscal_indicator["note"] = f"Fiscal Risk Score at {fiscal_score:.0f}. Extreme structural integrity and social stress risk."
        elif fiscal_score > 50.0:
            fiscal_indicator["status"] = "Amber"
            fiscal_indicator["note"] = f"Fiscal Risk Score at {fiscal_score:.0f}. Elevated risk from social stress and integrity factors."
        else:
            fiscal_indicator["status"] = "Green"
            fiscal_indicator["note"] = f"Fiscal Risk Score at {fiscal_score:.0f}. Risk is manageable based on current data."
        fiscal_indicator["action"] = "Monitor VIX and SNAP data closely."
    
    # 3. Compile OVERALL Score and Status
    score = composite_score
    overall_status_emoji = "🟢"
    overall_status_name = "LOW RISK"
    comment = "LOW RISK. Only minor triggers active. Favour moderate risk-on positioning."
    
    if score >= 6.0:
        overall_status_emoji = "🔴"
        overall_status_name = "HIGH RISK"
        comment = "HIGH RISK. Multiple severe triggers active. Aggressively hedge and reduce exposure."
    elif score >= 3.0:
        overall_status_emoji = "🟠"
        overall_status_name = "ELEVATED RISK"
        comment = "ELEVATED RISK. Key macro triggers active. Implement cautious hedging and watch credit markets."
    elif score >= 1.0:
        overall_status_emoji = "🟡"
        overall_status_name = "WATCH"
        comment = "WATCH. Minor triggers active. Monitor key risk signals closely."
    
    # 4. Update the Atlas Data Structure
    atlas_data["overall"] = {
        "date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "status": f"{overall_status_emoji} {overall_status_name}",
        "score": round(score, 2),
        "max_score": MAX_SCORE,
        "comment": comment,
        "composite_summary": "Overall risk posture is stable, but watch for credit signals.",
        "escalation_triggers": _compile_escalation_watch(atlas_data),
    }
    
    # 5. GENERATE THE AI ANALYSIS
    ai_commentary = generate_ai_commentary(atlas_data)

    # 6. INJECT THE ANALYSIS INTO THE DATA STRUCTURE
    if ai_commentary:
        atlas_data["overall"]["daily_narrative"] = ai_commentary
    else:
        atlas_data["overall"]["daily_narrative"] = f"AI Commentary failed to generate. Current status: {overall_status_name}. Score: {round(score, 2)}."

    # --- NEWS INTEGRATION ---
    print("Starting News Integration.")
    
    # Prioritize the full AI narrative for the search query, then the composite summary, then a generic phrase
    query_base = atlas_data["overall"].get("daily_narrative")
    if not query_base:
        query_base = atlas_data["overall"].get("composite_summary", "global economic risk")
        
    news_articles = fetch_news_articles(query_base)
    atlas_data["overall"]["news_articles"] = news_articles
    print(f"News Integration complete. Found {len(news_articles)} articles.")


    return atlas_data


# --- 4. DATA STRUCTURE (Initial State) ---
# Initial Data Schema (Used as a starting template)
ATLAS_DATA_SCHEMA = { 
    # Keys for the CURRENT run (used by the front-end)
    "date": datetime.datetime.now().strftime("%Y-%m-%d"),
    "atlas_score": 0.0,
    "current_status": "N/A",
    "last_updated": datetime.datetime.now().strftime("%I:%M %p").lower().lstrip('0'),
    
    # Macro Risk Indicators (Updated to Sentence Case names and added 'score' field)
    "macro": [
        {"id": "VIX", "name": "VIX index", "value": 0.0, "status": "N/A", "note": "", "action": "No change.", "score_value": 0.0, "source_link": ""},
        {"id": "GOLD_PRICE", "name": "Gold price (GLD)", "value": 0.0, "status": "N/A", "note": "", "action": "No change.", "score_value": 0.0, "source_link": ""},
        {"id": "EURUSD", "name": "EUR/USD exchange rate", "value": 0.0, "status": "N/A", "note": "", "action": "No change.", "score_value": 0.0, "source_link": ""},
        {"id": "WTI_CRUDE", "name": "WTI crude oil", "value": 0.0, "status": "N/A", "note": "", "action": "No change.", "score_value": 0.0, "source_link": ""},
        {"id": "AUDUSD", "name": "AUD/USD exchange rate", "value": 0.0, "status": "N/A", "note": "", "action": "No change.", "score_value": 0.0, "source_link": ""},
        {"id": "3Y_YIELD", "name": "US 3yr treasury yield", "value": 0.0, "status": "N/A", "note": "", "action": "No change.", "score_value": 0.0, "source_link": ""},
        {"id": "30Y_YIELD", "name": "US 30yr treasury yield", "value": 0.0, "status": "N/A", "note": "", "action": "No change.", "score_value": 0.0, "source_link": ""},
        {"id": "10Y_YIELD", "name": "US 10yr treasury yield", "value": 0.0, "status": "N/A", "note": "", "action": "No change.", "score_value": 0.0, "source_link": ""},
        {"id": "HY_OAS", "name": "High yield OAS (bps)", "value": 0.0, "status": "N/A", "note": "", "action": "No change.", "score_value": 0.0, "source_link": ""},
        {"id": "TREASURY_LIQUIDITY", "name": "Treasury net liquidity", "value": 0.0, "status": "N/A", "note": "Fed Balance - (TGA + ON RRP)", "action": "No change.", "score_value": 0.0, "source_link": ""},
        {"id": "GEOPOLITICAL", "name": "Geopolitical risk", "value": 0.0, "status": "N/A", "note": "Manual input score (0/0.5/1.0)", "action": "No change.", "score_value": 0.0, "source_link": ""},
        {"id": "FISCAL_RISK", "name": "Fiscal integrity risk", "value": 0.0, "status": "N/A", "note": "Composite score of VIX/SNAP/CPI.", "action": "No change.", "score_value": 0.0, "source_link": ""},
        {"id": "SNAP_BENEFITS", "name": "SNAP benefits (MoM)", "value": [0.0, 0.0], "status": "N/A", "note": "Dependency for Fiscal Risk", "action": "No change.", "score_value": 0.0, "source_link": ""},
    ],
    
    # Micro Risk Indicators (Updated to Sentence Case names and added 'score' field)
    "micro": [
        {"id": "SPX_INDEX", "name": "S&P 500 index", "value": 0.0, "status": "N/A", "note": "", "action": "No change.", "score_value": 0.0, "source_link": ""},
        {"id": "ASX_200", "name": "ASX 200 index", "value": 0.0, "status": "N/A", "note": "", "action": "No change.", "score_value": 0.0, "source_link": ""},
        {"id": "SOFR_OIS", "name": "SOFR/OIS spread", "value": 0.0, "status": "N/A", "note": "", "action": "No change.", "score_value": 0.0, "source_link": ""},
        {"id": "PUT_CALL_RATIO", "name": "Put/call ratio", "value": 0.0, "status": "N/A", "note": "", "action": "No change.", "score_value": 0.0, "source_link": ""},
        {"id": "MARGIN_DEBT_YOY", "name": "Margin debt (YOY)", "value": 0.0, "status": "N/A", "note": "", "action": "No change.", "score_value": 0.0, "source_link": ""},
        {"id": "SMALL_LARGE_RATIO", "name": "Small/large cap ratio", "value": 0.0, "status": "N/A", "note": "", "action": "No change.", "score_value": 0.0, "source_link": ""},
        {"id": "EARNINGS_REVISION", "name": "Earnings revision index", "value": "N/A", "status": "N/A", "note": "Not yet automated.", "action": "No change.", "score_value": 0.0, "source_link": ""},
        {"id": "BANK_CDS", "name": "Bank CDS spread", "value": 0.0, "status": "N/A", "note": "", "action": "No change.", "score_value": 0.0, "source_link": ""},
        {"id": "CONSUMER_DELINQUENCIES", "name": "Consumer delinquencies", "value": 0.0, "status": "N/A", "note": "", "action": "No change.", "score_value": 0.0, "source_link": ""},
    ],
    
    # Placeholder for the final overall status (filled by run_update_process)
    "overall": {}
}


# --- 5. EXECUTION ---
if __name__ == "__main__":
    # 1. Initialize data structure
    atlas_data = ATLAS_DATA_SCHEMA 

    # 2. Update Source Links
    atlas_data["macro"] = _update_indicator_sources(atlas_data["macro"])
    atlas_data["micro"] = _update_indicator_sources(atlas_data["micro"])

    # 3. FETCH RAW DATA
    print("Fetching data from all accredited APIs...")
    all_indicators = atlas_data["macro"] + atlas_data["micro"]
    
    # Create the data directory if it doesn't exist (CRITICAL FIX)
    if not os.path.exists("data"):
        os.makedirs("data")
        print("Created data/ directory.")

    for indicator in all_indicators:
        indicator_id = indicator["id"]
        
        # Skip indicators that are PURELY MANUAL (GEOPOLITICAL) or COMPOSITES (FISCAL_RISK)
        # SNAP_BENEFITS must be fetched here as it is a dependency for FISCAL_RISK
        if indicator_id in ["GEOPOLITICAL", "FISCAL_RISK"]:
            print(f"Skipped: {indicator_id} is a manual/calculated input.")
            if indicator_id == "GEOPOLITICAL":
                 # Set a default manual score (e.g., green/stable)
                 indicator["value"] = 0.0 
        else:
            # Fetch the raw value using the appropriate API/FRED/YFinance logic
            indicator["value"] = fetch_indicator_data(indicator["id"])
            
    print("Data fetching complete. Starting scoring process.")

    # 4. RUN MAIN PROCESS (Scoring, Narrative, and Saving)
    try:
        # run_update_process is now defined above
        updated_atlas_data = run_update_process(atlas_data)
        
        # Save the Final Results to the main output file
        with open(OUTPUT_FILE, 'w') as f:
            json.dump(updated_atlas_data, f, indent=4) 
        print(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Success: Atlas JSON successfully generated and written to {OUTPUT_FILE}")

        # Save the narrative/summary to the archive file
        save_to_archive(updated_atlas_data["overall"])
        
    except Exception as e:
        print(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] FATAL ERROR: Atlas update failed. Error: {e}")
        # Log the full traceback if possible, but for deployment keep simple
        # import traceback; traceback.print_exc()