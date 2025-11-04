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

# --- CONFIGURATION ---

# 1. Output File Path (Must match your front-end fetch)
OUTPUT_FILE = "data/atlas-latest.json" 
# NEW: Archive File Path for infinite scroll
ARCHIVE_FILE = "data/atlas-archive.json" 

# 2. API Keys and Endpoints (Placeholder structure)
# WARNING: Store real keys securely (e.g., environment variables)
API_CONFIG = {
    # 1. LIVE FRED KEY & ENDPOINT
    "FRED_API_KEY": "932518e735c7846a788c5fb8f01f1f89", # <-- USE YOUR ACTUAL KEY
    "FRED_ENDPOINT": "https://api.stlouisfed.org/fred/series/observations",
  
    # 2. EXTERNAL API KEYS & ENDPOINTS
    "VIX_API_KEY": "5CGATLAPOEYLJTO7",      
    "VIX_ENDPOINT": "https://www.alphavantage.co/query", 
    
    "GOLD_API_KEY": "5CGATLAPOEYLJTO7",      
    "GOLD_ENDPOINT": "https://www.alphavantage.co/query", 
    
    "FX_API_KEY": "5CGATLAPOEYLJTO7",      
    "FX_ENDPOINT": "https://www.alphavantage.co/query", 
    
    "WTI_API_KEY": "5CGATLAPOEYLJTO7",      
    "WTI_ENDPOINT": "https://www.alphavantage.co/query",
    
    "EQUITY_API_KEY": "5CGATLAPOEYLJTO7", 
    "EQUITY_ENDPOINT": "https://www.alphavantage.co/query",
    
    # Options/Sentiment API (LIVE - Polygon)
    "PUT_CALL_API_KEY": "qYLFTWtQSFs3NntmnCeQDy8d5asiA6_3",      # <-- YOUR LIVE KEY
    "PUT_CALL_ENDPOINT": "https://api.polygon.io/v2/aggs/ticker/PCCE/prev", 
    
    # Credit/CDS API (Still Placeholder - will use "N/A" logic)
    "CREDIT_API_KEY": "YOUR_CREDIT_KEY_HERE",
    "CREDIT_ENDPOINT": "YOUR_CREDIT_API_ENDPOINT",

    # Earnings/Analyst API (Still Placeholder - will use "N/A" logic)
    "EARNINGS_API_KEY": "YOUR_EARNINGS_KEY_HERE",
    "EARNINGS_ENDPOINT": "YOUR_EARNINGS_API_ENDPOINT", 
    
    
    # 3. FRED SERIES IDS
    "FRED_3YR_ID": "DGS3",
    "FRED_30YR_ID": "DGS30",
    "FRED_10YR_ID": "DGS10",  
    "FRED_HYOAS_ID": "BAMLH0A0HYM2", 
    "FRED_SOFR_3M_ID": "TB3MS",      
    "FRED_EFFR_ID": "EFFR",             
    "FRED_WALCL_ID": "WALCL",           
    
    "FRED_WTREGEN_ID": "WTREGEN",      
    "FRED_RRPONTSYD_ID": "RRPONTSYD",   
    "FRED_BANK_CDS_ID": "AAA", 
    
    "FRED_CONSUMER_DELINQ_ID": "DRCCLACBS", 
    "FRED_SNAP_ID": "TRP6001A027NBEA", # CORRECT FRED ID for Total SNAP Participants (Fixes previous error)
}

# Initialize FRED client only if the key is available
FRED_API_KEY = API_CONFIG.get("FRED_API_KEY")
if FRED_API_KEY and FRED_API_KEY != "YOUR_FRED_KEY_HERE":
    fred = Fred(api_key=FRED_API_KEY)
else:
    fred = None 
    print("Warning: FRED_API_KEY is missing or invalid. FRED-based indicators will return fallbacks.")


# --- NEW INDICATOR FUNCTIONS (Treasury Liquidity, Margin Debt, SOFR/OIS) ---

def get_treasury_net_liquidity():
    """
    Calculates Treasury Net Liquidity: Fed Balance Sheet - (TGA + ON RRP).
    Sources: WALCL (Weekly), WTREGEN (Daily), RRPONTSYD (Daily). Result is in Billions USD.
    """
    if not fred:
        print("FRED client not initialized. Cannot fetch Treasury Liquidity.")
        return 0.0

    try:
        # Fetch the most recent data point for each component (all in Millions USD)
        walcl = fred.get_series_latest_release(API_CONFIG["FRED_WALCL_ID"]).iloc[-1]
        wtregen = fred.get_series_latest_release(API_CONFIG["FRED_WTREGEN_ID"]).iloc[-1]
        rrpontsyd = fred.get_series_latest_release(API_CONFIG["FRED_RRPONTSYD_ID"]).iloc[-1]

        # Calculation: Net Liquidity = WALCL - (WTREGEN + RRPONTSYD)
        net_liquidity = walcl - (wtregen + rrpontsyd)
        
        # Return the result in Billions (dividing by 1000)
        return round(net_liquidity / 1000, 2)

    except Exception as e:
        print(f"FRED API Error for Net Liquidity: {e}")
        return 0.0 # Fallback value


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
    Calculates the SOFR/EFFR Spread (proxy for SOFR OIS Spread).
    The spread is 3-Month Compounded SOFR Average minus the Effective Federal Funds Rate (EFFR).
    Sources: SOFR3MAD and EFFR.
    Result is in Basis Points.
    """
    if not fred:
        print("FRED client not initialized. Cannot fetch SOFR OIS Spread.")
        return 0.0

    try:
        # 3-Month Compounded SOFR Average (Daily)
        sofr_3m = fred.get_series_latest_release(API_CONFIG["FRED_SOFR_3M_ID"]).iloc[-1]
        
        # Effective Federal Funds Rate (EFFR - Daily)
        effr = fred.get_series_latest_release(API_CONFIG["FRED_EFFR_ID"]).iloc[-1]
    
        # Calculate the spread and convert to basis points (x 100)
        spread = (sofr_3m - effr) * 100
        
        return round(spread, 2) 

    except Exception as e:
        print(f"FRED API Error for SOFR OIS Spread: {e}")
        return 0.0 # Fallback value


# --- NEW FUNCTION: AI Commentary Generator ---
def generate_ai_commentary(data_dict):
    """Generates the 1-2 paragraph AI Analyst Commentary."""
    
    # The client automatically picks up the GEMINI_API_KEY from your environment!
    try:
        client = genai.Client()
    except Exception as e:
        print(f"Error initializing Gemini client: {e}. Check your GEMINI_API_KEY environment variable.")
        return None

    # 1. Prepare the Prompt with all the data
    # We will use the final JSON data as the context for the AI
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

    # 2. Configure the API Call
    config = types.GenerateContentConfig(
        system_instruction=system_instruction,
        temperature=0.3, # Lower temperature for factual, consistent output
    )

    # 3. Call the Gemini API
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

def _fetch_fred_data_two_points(fred_id, fred_api_key):
    """Fetches the last two observation values for a given FRED series."""
    try:
        fred = Fred(api_key=fred_api_key)
        # Fetch the entire series as a Pandas Series
        series_data = fred.get_series(fred_id)
        
        if series_data is None or series_data.empty or len(series_data) < 2:
            print(f"Warning: FRED series {fred_id} returned less than 2 data points or does not exist.")
            # Return fallback list [0.0, 0.0] if data is bad
            return [0.0, 0.0]
           
        # Get the last two values as a list: [Previous Month, Current Month]
        last_two_values = series_data.tail(2).values.tolist()
        
        # FRED data can sometimes be represented as strings/objects, ensure float conversion
        return [float(last_two_values[0]), float(last_two_values[1])]
        
    except Exception as e:
        print(f"Error fetching FRED data for {fred_id}: {e}")
        # Return fallback list [0.0, 0.0] on API error
        return [0.0, 0.0]
    

def fetch_indicator_data(indicator_id):
    """
    Fetches the latest data for all indicators, routing to FRED, new live functions, 
    or external APIs, and returns "N/A" for unautomated indicators.
    """
    
    # Define a safe fallback value for FRED series 
    FRED_FALLBACK_VALUE = {
        "3Y_YIELD": 3.50, "30Y_YIELD": 4.25, "10Y_YIELD": 4.30, "HY_OAS": 380.0,
        # Fallbacks for the new calculated FRED indicators
        "TREASURY_LIQUIDITY": 100.0,
        "SOFR_OIS": 25.0,
        "BANK_CDS": 85.0,
        "CONSUMER_DELINQUENCIES": 2.2, 
    }

    # ----------------------------------------------------------------------
    # --- FRED API CALLS (For Yields and HY_OAS - Single-Point Fetch) ---
    # ----------------------------------------------------------------------
    fred_series_map = {
        "3Y_YIELD": API_CONFIG["FRED_3YR_ID"], 
        "30Y_YIELD": API_CONFIG["FRED_30YR_ID"],
        "10Y_YIELD": API_CONFIG["FRED_10YR_ID"], 
        "HY_OAS": API_CONFIG["FRED_HYOAS_ID"],
        "BANK_CDS": API_CONFIG["FRED_BANK_CDS_ID"], 
        "CONSUMER_DELINQUENCIES": API_CONFIG["FRED_CONSUMER_DELINQ_ID"], 
    }

    
    if indicator_id in fred_series_map:
        series_id = fred_series_map[indicator_id]
        fallback = FRED_FALLBACK_VALUE.get(indicator_id, 0.0)
        
        try:
            params = {
                "series_id": series_id, "api_key": API_CONFIG["FRED_API_KEY"],
                "file_type": "json", 
                "observation_start": (datetime.date.today() - datetime.timedelta(days=365*3)).strftime("%Y-%m-%d"),
                "sort_order": "desc", "limit": 1
            }
            response = requests.get(API_CONFIG["FRED_ENDPOINT"], params=params)
            response.raise_for_status() 
            data = response.json()
            
            for obs in data.get("observations", []):
                if obs["value"] != ".":
                    return float(obs["value"]) 
            
            print(f"FRED Warning: No valid data found for {indicator_id}. Returning fallback value {fallback}.")
            return fallback

        except requests.exceptions.RequestException as e:
            print(f"FRED Error fetching {indicator_id}: {e}. Returning fallback value {fallback}.")
            return fallback

    # ----------------------------------------------------------------------
    # --- CUSTOM FRED API CALLS (Multi-Point Fetch) ------------------------
    # ----------------------------------------------------------------------
    
    # NEW: FRED - Supplemental Nutrition Assistance Program (SNAP)
    elif indicator_id == "SNAP_BENEFITS":
        # Uses the helper function to fetch [Previous Month, Current Month]
        fred_id = API_CONFIG.get("FRED_SNAP_ID", "SNPTA") 
        return _fetch_fred_data_two_points(fred_id, API_CONFIG["FRED_API_KEY"]) 
            
    # ----------------------------------------------------------------------
    # --- LIVE CALCULATED INDICATORS (NEW) ---------------------------------
    # ----------------------------------------------------------------------
    
    # Macro Indicators
    elif indicator_id == "TREASURY_LIQUIDITY":
        # LIVE CALL: Net Liquidity (Calculated from FRED)
        return get_treasury_net_liquidity()

    # Micro Indicators
    elif indicator_id == "SOFR_OIS": 
        # LIVE CALL: SOFR OIS Spread (Calculated from FRED)
        return get_sofr_ois_spread()
    elif indicator_id == "MARGIN_DEBT_YOY": 
        # LIVE CALL: Margin Debt YOY (Calculated from FINRA Excel)
        return get_finra_margin_debt_yoy()

  
    # ----------------------------------------------------------------------
    # --- EXTERNAL API CALLS (Remaining) -----------------------------------
    # ----------------------------------------------------------------------
    
    # VIX and Indices (YFinance)
    elif indicator_id in ["VIX", "GOLD_PRICE", "EURUSD", "WTI_CRUDE", "AUDUSD", 
                          "SPX_INDEX", "ASX_200", "SMALL_LARGE_RATIO"]: 
        
        # Use a placeholder value as the fallback for fetch_external_data
        fallback_map = {
            "VIX": 22.0, "GOLD_PRICE": 2000.00, "EURUSD": 1.14, "WTI_CRUDE": 80.0, 
            "AUDUSD": 0.68, "SPX_INDEX": 4400.0, "ASX_200": 8600.0, "SMALL_LARGE_RATIO": 0.42
        }
        return fetch_external_data("FX_ENDPOINT", "FX_API_KEY", indicator_id, fallback_map.get(indicator_id, 0.0))

    # Put/Call Ratio (Polygon)
    elif indicator_id == "PUT_CALL_RATIO": 
        return fetch_external_data("PUT_CALL_ENDPOINT", "PUT_CALL_API_KEY", "PUT_CALL_RATIO", 0.9)
    
    
    # ----------------------------------------------------------------------
    # --- UNIMPLEMENTED PLACEHOLDERS (Return "N/A") ------------------------
    # ----------------------------------------------------------------------
    # FISCAL_RISK and GEOPOLITICAL are handled by the main loop, but if reached, they return N/A
    elif indicator_id in ["EARNINGS_REVISION", "BANK_CDS", "CONSUMER_DELINQUENCIES", "GEOPOLITICAL", "FISCAL_RISK"]: 
        return "N/A" 
    
    return None # Should not be reached

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

def _fetch_polygon_data(endpoint, api_key):
    """Internal function to fetch Put/Call Ratio data from the Polygon.io 'prev' endpoint."""
    params = {
        "apiKey": api_key
    }
    
    response = requests.get(endpoint, params=params)
    response.raise_for_status() 
    data = response.json()
    
    results = data.get("results")
    if not results or not isinstance(results, list) or len(results) == 0:
         raise ValueError("Polygon API results array is empty or missing.")

    pcr_value = results[0].get("c") 

    if pcr_value is None:
         raise ValueError("Polygon API data parsing failed: 'c' (close) price is missing in the result.")
         
    return float(pcr_value)

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
    
    if indicator_id in ["VIX", "GOLD_PRICE", "SPX_INDEX", "ASX_200", 
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

    if value <= 4200.0:
        status = "Red"
        note = f"S&P 500 Index at {value:,.0f}. Aggressive sell-off/Correction >12%. Structural equity risk is high."
        action = "Sell/Hedge significant equity exposure. Wait for VIX confirmation below 22."
        score = 1.0
    elif value <= 4500.0:
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
    """Treasury Net Liquidity Scoring - Measures system-wide funding/liquidity risk."""
    status = "Green"
    note = f"Net Liquidity at ${value:.0f}B. Sufficient systemic liquidity."
    action = "No change."
    score = 0.0
    source_link = "https://fred.stlouisfed.org/series/WALCL"

    if isinstance(value, str):
        if value.upper() == 'N/A':
            return generate_score_output("N/A", "Data N/A: Treasury Liquidity requires FRED data.", "Cannot score due to missing data.", 0.0, source_link)
        try:
            value = float(value)
        except ValueError:
            return generate_score_output("Error", "Error: Liquidity value could not be converted to number.", "Cannot score due to data error.", 0.0, "")

    if value <= 100.0:
        status = "Red"
        note = f"Net Liquidity at ${value:.0f}B. Systemic liquidity is being severely drained. High risk of funding shock."
        score = 2.5
        action = "Aggressively increase cash reserves and reduce short-term debt exposure."
    elif value <= 300.0:
        status = "Amber"
        note = f"Net Liquidity at ${value:.0f}B. Liquidity is tightening. Monitor short-term rates and counterparty risk."
        score = 1.5
        action = "Reduce leverage and monitor short-term funding rates."

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
            return generate_score_output("N/A", "Data N/A: Put/Call Ratio requires external API.", "Cannot score due to missing data.", 0.0, source_link)
        try:
            value = float(value)
        except ValueError:
            return generate_score_output("Error", "Error: Put/Call value could not be converted to number.", "Cannot score due to data error.", 0.0, "")

    if isinstance(value, float):
        if value >= 1.2:
            status = "Amber"
            note = f"Put/Call Ratio at {value:.2f}. High put volume suggests bearish sentiment, which can be contrarian bullish."
            score = 0.5 # A low-risk positive signal
            action = "Watch for technical reversal signals."
        elif value <= 0.8:
            status = "Amber"
            note = f"Put/Call Ratio at {value:.2f}. Low put volume suggests complacency/overbought conditions."
            score = 0.5
            action = "Avoid adding new long equity exposure."
        
    return generate_score_output(status, note, action, score, source_link)


def score_small_large_ratio(value):
    """Small Cap / Large Cap Ratio Scoring - Measures market internals/breadth."""
    status = "Red"
    note = f"Ratio at {value:.2f} — small-caps underperforming. Internals fragile."
    action = "Avoid growth/cyclical exposure; favour quality/large-cap."
    score = 1.0
    source_link = "https://finance.yahoo.com/quote/%5ERUT"

    if isinstance(value, str):
        if value.upper() == 'N/A':
            return generate_score_output("N/A", "Data N/A: Small/Large Ratio requires YFinance.", "Cannot score due to missing data.", 0.0, source_link)
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
    """Earnings Revision Index Scoring (Micro Indicator - Placeholder for net analyst revisions)."""
    status = "Amber"
    note = "Earnings revisions are stable."
    action = "Monitor analyst expectations."
    score = 0.5
    source_link = "N/A" # Placeholder for future Earnings API

    if isinstance(value, str):
        if value.upper() == 'N/A':
            return generate_score_output("N/A", "Data N/A: Earnings revision requires external API.", "Cannot score due to missing data.", 0.0, source_link)
        try:
            value = float(value)
        except ValueError:
            return generate_score_output("Error", "Error: Earnings revision value could not be converted to number.", "Cannot score due to data error.", 0.0, "")

    if isinstance(value, float):
        note = f"{value:.0f}% net revisions. Earnings weakening."
        if value <= -5.0:
            status = "Red"
            note = f"{value:.0f}% net revisions. Widespread negative revisions; structural earnings risk is high."
            score = 1.0
            action = "Avoid highly cyclical/growth stocks until revisions stabilize."
        elif value >= 0.0:
            status = "Green"
            note = f"{value:.0f}% net revisions. Positive or neutral revisions; earnings are supporting the market."
            score = 0.0
            action = "No change."

    return generate_score_output(status, note, action, score, source_link)


def score_margin_debt_yoy(value):
    """FINRA Margin Debt Year-over-Year Scoring (Micro Indicator)."""
    status = "Amber"
    note = "Leverage is stable."
    action = "Monitor debt metrics."
    score = 0.5
    source_link = "https://www.finra.org/investors/market-and-financial-data/margin-statistics"

    if isinstance(value, str):
        if value.upper() == 'N/A':
            return generate_score_output("N/A", "Data N/A: Margin debt requires external API.", "Cannot score due to missing data.", 0.0, source_link)
        try:
            value = float(value)
        except ValueError:
            return generate_score_output("Error", "Error: Margin debt value could not be converted to number.", "Cannot score due to data error.", 0.0, "")

    if isinstance(value, float):
        if value >= 10.0:
            status = "Red"
            note = f"Margin Debt YoY at {value:.1f}%. Extreme leverage growth. Implies high liquidation risk."
            score = 1.0
            action = "Reduce leveraged positions. Watch for technical weakness."
        elif value <= -10.0:
            status = "Green"
            note = f"Margin Debt YoY at {value:.1f}%. Leverage has been aggressively reduced. Potential for risk-on recovery."
            score = 0.0
            action = "Look for opportunities in high-beta/growth sectors."
        # Default Amber status covers the middle range
        
    return generate_score_output(status, note, action, score, source_link)


def score_bank_cds(value):
    """Bank CDS Index Scoring (Micro Indicator - Placeholder for US Banking Risk)."""
    status = "Green"
    note = f"Bank CDS Index at {value:.0f} bps. Low implied banking risk."
    action = "No change."
    score = 0.0
    source_link = "https://www.fred.stlouisfed.org/series/AAA" # Placeholder for a FRED series

    if isinstance(value, str):
        if value.upper() == 'N/A':
            return generate_score_output("N/A", "Data N/A: Bank CDS Index requires external API.", "Cannot score due to missing data.", 0.0, source_link)
        try:
            value = float(value)
        except ValueError:
            return generate_score_output("Error", "Error: Bank CDS value could not be converted to number.", "Cannot score due to data error.", 0.0, "")

    if isinstance(value, float):
        if value >= 150.0:
            status = "Red"
            note = f"Bank CDS Index at {value:.0f} bps. High implied banking risk. Indicates significant counterparty fear."
            score = 2.0
            action = "Aggressively reduce financial sector exposure and monitor interbank lending markets."
        elif value >= 100.0:
            status = "Amber"
            note = f"Bank CDS Index at {value:.0f} bps. Elevated implied banking risk. Monitor closely."
            score = 1.0
            action = "Monitor financial sector credit and solvency closely."
        # Default Green status covers the lower range
        
    return generate_score_output(status, note, action, score, source_link)


def score_consumer_delinquencies(value):
    """Consumer Delinquency Rate Scoring (Micro Indicator)."""
    status = "Green"
    note = "Household debt stress is low."
    action = "No change."
    score = 0.0
    source_link = "https://fred.stlouisfed.org/series/DRCCLACBS"

    if isinstance(value, str):
        if value.upper() == 'N/A':
            return generate_score_output("N/A", "Data N/A: Consumer Delinquency data requires external API.", "Cannot score due to missing data.", 0.0, source_link)
        try:
            value = float(value)
        except ValueError:
            return generate_score_output("Error", "Error: Delinquency value could not be converted to number.", "Cannot score due to data error.", 0.0, "")

    if isinstance(value, float):
        if value >= 3.8:
            status = "Red"
            note = f"Delinquency Rate at {value:.1f}%. Aggressively high rate. Indicates significant household stress and consumer spending risk."
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
    prev_month_snap = snap_values[0] 
    current_month_snap = snap_values[1]
    snap_score = 5 # Default: Low Risk
    
    # Calculate MoM Change as a Percentage
    if prev_month_snap > 0 and current_month_snap > 0:
        mom_change_percent = ((current_month_snap - prev_month_snap) / prev_month_snap) * 100
    else:
        # If data is missing (0.0, 0.0), assume high risk for integrity score
        mom_change_percent = 0
        snap_score = 25 if prev_month_snap == 0 and current_month_snap == 0 else 5
        
    # Scoring Logic
    if abs(mom_change_percent) >= 5.0: 
        snap_score = 25 # Major disruption or major, unexpected stimulus
    elif abs(mom_change_percent) >= 2.5: 
        snap_score = 15 # Moderate instability
    else:
        snap_score = 5 

    # ----------------------------------------------------------------------
    # 2. Structural Integrity (Corruption Perception Index Placeholder) - MAX 25
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
    if "meta" not in atlas_data: atlas_data["meta"] = {}
    atlas_data["meta"]["fiscal_breakdown"] = {
        "snap_score": snap_score,
        "corruption_score": round(corruption_score, 2),
        "civil_unrest_score": civil_unrest_score,
        "reg_confidence_score": reg_confidence_score
    }
    
    # NOTE: This function returns a float, which is why the main loop failed previously.
    return round(total_fiscal_risk_score, 2)


# --- DICTIONARY MAPPING INDICATOR ID TO SCORING FUNCTION (NEW CORRECT LOCATION) ---
SCORING_FUNCTIONS = {
    # MACRO Indicators
    "VIX": score_vix, "GOLD_PRICE": score_gold_price, "EURUSD": score_eurusd, 
    "WTI_CRUDE": score_wti_crude, "AUDUSD": score_audusd, "3Y_YIELD": score_3y_yield, 
    "30Y_YIELD": score_30y_yield, "10Y_YIELD": score_10y_yield, "HY_OAS": score_hy_oas,
    "TREASURY_LIQUIDITY": score_treasury_liquidity,
    
    # MICRO Indicators
    "SPX_INDEX": score_spx_index, "ASX_200": score_asx_200, "SOFR_OIS": score_sofr_ois,
    "PUT_CALL_RATIO": score_put_call_ratio, "SMALL_LARGE_RATIO": score_small_large_ratio,
    "EARNINGS_REVISION": score_earnings_revision, "MARGIN_DEBT_YOY": score_margin_debt_yoy,
    "BANK_CDS": score_bank_cds, "CONSUMER_DELINQUENCIES": score_consumer_delinquencies,

    # Composite/Manual
    "GEOPOLITICAL": score_geopolitical,
    "FISCAL_RISK": score_fiscal_risk, 
}

# --- WATCHLIST THRESHOLDS ---
# Defines the thresholds that trigger an "Escalation Watch" flag
WATCH_INDICATORS = {
    "HY_OAS": {"name": "HY OAS", "threshold": 350.0, "threshold_desc": "Above 350 bps"},
    "SOFR_OIS": {"name": "SOFR/OIS Spread", "threshold": 25.0, "threshold_desc": "Above 25 bps"},
    "TREASURY_LIQUIDITY": {"name": "Net Liquidity", "threshold": 300.0, "threshold_desc": "Below $300B"},
    "VIX": {"name": "VIX", "threshold": 18.0, "threshold_desc": "Above 18.0"},
    "10Y_YIELD": {"name": "10-Year Yield", "threshold": 4.0, "threshold_desc": "Above 4.0%"},
}

def _compile_escalation_watch(atlas_data):
    """Compiles a list of indicators that have breached their Amber/Red thresholds."""
    all_indicators = {item['id']: item for item in atlas_data['macro'] + atlas_data['micro']}
    escalation_list = []
    
    for indicator_id, watch_info in WATCH_INDICATORS.items():
        if indicator_id in all_indicators:
            indicator = all_indicators[indicator_id]
            current_value = indicator.get("value")
            
            # Check the condition for Amber/Red state
            is_breached = False
            if indicator_id in ["TREASURY_LIQUIDITY"] and isinstance(current_value, (int, float)) and current_value <= watch_info["threshold"]:
                is_breached = True # Low is bad
            elif indicator_id in ["HY_OAS", "SOFR_OIS", "VIX", "10Y_YIELD"] and isinstance(current_value, (int, float)) and current_value >= watch_info["threshold"]:
                is_breached = True # High is bad

            if is_breached:
                # Format the current reading appropriately
                if isinstance(current_value, (int, float)):
                    if indicator_id in ["HY_OAS", "BANK_CDS"]: 
                        formatted_value = f"{current_value:.0f}"
                    elif indicator_id in ["SOFR_OIS", "VIX"]: 
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


# --- 3. MAIN PROCESSOR ---

def run_update_process(atlas_data):
    """
    Core logic to apply scoring, calculate composites, and generate the final output.
    """
    composite_score = 0.0
    
    all_indicators = atlas_data["macro"] + atlas_data["micro"]

    # 1. SCORE ALL INDICATORS (Except FISCAL_RISK)
    for indicator in all_indicators:
        indicator_id = indicator["id"]
        
        # Skip the composite FISCAL_RISK indicator in this loop (FIXES THE TypeError)
        if indicator_id == "FISCAL_RISK" or indicator_id == "SNAP_BENEFITS":
            continue
            
        scoring_func = SCORING_FUNCTIONS.get(indicator_id)
        
        if scoring_func:
            # Special case for GEOPOLITICAL: it takes the pre-fetched value as input
            if indicator_id == "GEOPOLITICAL":
                geopolitical_value = indicator.get("value") 
                if not isinstance(geopolitical_value, (int, float)):
                     geopolitical_value = 0.0
                result = scoring_func(geopolitical_value)
            # All other standard indicators take their 'value' as input
            else:
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
            # Ensure manual/unscored indicators have a default score of 0
            indicator["score_value"] = 0
            
    # --- 1B. CALCULATE AND SCORE FISCAL_RISK (Special Case to avoid TypeError) ---
    fiscal_indicator = next((item for item in all_indicators if item["id"] == "FISCAL_RISK"), None)
    if fiscal_indicator:
        # result here is the score (float)
        fiscal_score = score_fiscal_risk(atlas_data)
        
        fiscal_indicator["value"] = fiscal_score # Store the score in the value field
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
        
        # FISCAL_RISK score is NOT added to the composite_score (as per original logic intent)

    # 2. Determine Overall Status (Based on Thresholds)
    MAX_SCORE = 22.5
    score = composite_score
    
    if score > 12.0:
        overall_status_emoji = "🚨" 
        overall_status_name = "FULL-STORM"
        comment = "EXTREME RISK. Multiple systemic and funding triggers active. Maintain maximum defensive posture."
    elif score > 8.0:
        overall_status_emoji = "🔴" 
        overall_status_name = "SEVERE RISK"
        comment = "HIGH RISK. Significant Macro and/or Micro triggers active. Aggressively increase liquidity and hedges (Storm Posture)."
    elif score > 4.0:
        overall_status_emoji = "🟠" 
        overall_status_name = "ELEVATED RISK"
        comment = "MODERATE RISK. Core volatility/duration triggers active. Proceed with caution; maintain protective hedges."
    else:
        overall_status_emoji = "🟢" 
        overall_status_name = "MONITOR"
        comment = "LOW RISK. Only minor triggers active. Favour moderate risk-on positioning."

    # 3. Update the Atlas Data Structure
    atlas_data["overall"]["date"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    atlas_data["overall"]["status"] = f"{overall_status_emoji} {overall_status_name}"
    atlas_data["overall"]["score"] = round(score, 2)
    atlas_data["overall"]["max_score"] = MAX_SCORE
    atlas_data["overall"]["comment"] = comment
    atlas_data["overall"]["composite_summary"] = "Overall risk posture is stable, but watch for credit signals." # Placeholder
    atlas_data["overall"]["escalation_triggers"] = _compile_escalation_watch(atlas_data) # NEW LINE ADDED TO FIX THE ERROR
    
    # 4. GENERATE THE AI ANALYSIS (Calls Gemini)
    ai_commentary = generate_ai_commentary(atlas_data)

    # 5. INJECT THE ANALYSIS INTO THE DATA STRUCTURE
    if ai_commentary:
        # This will be the 1-2 paragraph synthesis generated by Gemini
        atlas_data["overall"]["daily_narrative"] = ai_commentary
    else:
        # Fallback to a simple message if the API call fails
        atlas_data["overall"]["daily_narrative"] = f"AI Commentary failed to generate. Current status: {overall_status_name}. Score: {round(score, 2)}."

    return atlas_data


# --- 4. DATA STRUCTURE (Initial State) ---

ATLAS_DATA_SCHEMA = {
    "overall": {
        "date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "status": "N/A",
        "score": 0.0,
        "max_score": 22.5,
        "comment": "Initializing...",
        "composite_summary": "",
        "daily_narrative": "",
        "escalation_triggers": []
    },
    "meta": {
        "run_time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "fiscal_breakdown": {}
    },
    "macro": [
        # Macro Risk Indicators (Systemic / High Impact)
        {"id": "VIX", "name": "VIX Index", "value": 0.0, "status": "N/A", "note": "", "action": "No change.", "source_link": ""},
        {"id": "GOLD_PRICE", "name": "Gold Price (GLD)", "value": 0.0, "status": "N/A", "note": "", "action": "No change.", "source_link": ""},
        {"id": "EURUSD", "name": "EUR/USD", "value": 0.0, "status": "N/A", "note": "", "action": "No change.", "source_link": ""},
        {"id": "WTI_CRUDE", "name": "WTI Crude Oil", "value": 0.0, "status": "N/A", "note": "", "action": "No change.", "source_link": ""},
        {"id": "AUDUSD", "name": "AUD/USD", "value": 0.0, "status": "N/A", "note": "", "action": "No change.", "source_link": ""},
        {"id": "3Y_YIELD", "name": "3-Year Yield", "value": 0.0, "status": "N/A", "note": "", "action": "No change.", "source_link": ""},
        {"id": "30Y_YIELD", "name": "30-Year Yield", "value": 0.0, "status": "N/A", "note": "", "action": "No change.", "source_link": ""},
        {"id": "10Y_YIELD", "name": "10-Year Yield", "value": 0.0, "status": "N/A", "note": "", "action": "No change.", "source_link": ""},
        {"id": "HY_OAS", "name": "HY OAS (Credit Risk)", "value": 0.0, "status": "N/A", "note": "", "action": "No change.", "source_link": ""},
        {"id": "TREASURY_LIQUIDITY", "name": "Net Treasury Liquidity", "value": 0.0, "status": "N/A", "note": "", "action": "No change.", "source_link": ""},
        
        # Composite / Manual Input
        {"id": "FISCAL_RISK", "name": "Fiscal Integrity Risk", "value": 0.0, "status": "N/A", "note": "Composite score of VIX/SNAP/CPI.", "action": "No change.", "source_link": ""},
        {"id": "SNAP_BENEFITS", "name": "SNAP Benefits (MoM)", "value": [0.0, 0.0], "status": "N/A", "note": "Dependency for Fiscal Risk", "action": "No change.", "source_link": ""}, # Dependency indicator
    ],
    "micro": [
        # Micro Risk Indicators (Equity/Sentiment/Sector)
        {"id": "SPX_INDEX", "name": "S&P 500 Index", "value": 0.0, "status": "N/A", "note": "", "action": "No change.", "source_link": ""},
        {"id": "ASX_200", "name": "ASX 200 Index", "value": 0.0, "status": "N/A", "note": "", "action": "No change.", "source_link": ""},
        {"id": "SOFR_OIS", "name": "SOFR/OIS Spread", "value": 0.0, "status": "N/A", "note": "", "action": "No change.", "source_link": ""},
        {"id": "PUT_CALL_RATIO", "name": "Put/Call Ratio", "value": 0.0, "status": "N/A", "note": "", "action": "No change.", "source_link": ""},
        {"id": "SMALL_LARGE_RATIO", "name": "Small/Large Cap Ratio", "value": 0.0, "status": "N/A", "note": "", "action": "No change.", "source_link": ""},
        
        # Placeholder Indicators
        {"id": "EARNINGS_REVISION", "name": "Earnings Revision Index", "value": "N/A", "status": "N/A", "note": "", "action": "No change.", "source_link": "N/A"},
        {"id": "MARGIN_DEBT_YOY", "name": "Margin Debt YoY %", "value": 0.0, "status": "N/A", "note": "", "action": "No change.", "source_link": ""},
        {"id": "BANK_CDS", "name": "Bank CDS Index", "value": "N/A", "status": "N/A", "note": "", "action": "No change.", "source_link": "N/A"},
        {"id": "CONSUMER_DELINQUENCIES", "name": "Consumer Delinquencies", "value": "N/A", "status": "N/A", "note": "", "action": "No change.", "source_link": "N/A"},
        
        # Manual Input
        {"id": "GEOPOLITICAL", "name": "Geopolitical Risk", "value": 0.0, "status": "N/A", "note": "Manual input: 0.0=Stable, 0.5=Elevated, 1.0=Severe", "action": "No change.", "source_link": "Manual Input/Qualitative Assessment"},
    ],
    "short_insight": [{"text": "Global equity risk remains muted despite rising long-end yields."}],
}


# --- 5. EXECUTION ---

def main():
    """Main function to run the Atlas data update process."""
    
    # 1. Load Initial Schema (or existing data if needed, but we use schema for simplicity)
    atlas_data = ATLAS_DATA_SCHEMA
    
    # 2. Update Source Links
    atlas_data["macro"] = _update_indicator_sources(atlas_data["macro"])
    atlas_data["micro"] = _update_indicator_sources(atlas_data["micro"])
    
    # 3. FETCH RAW DATA
    print("Fetching data from all accredited APIs...")
    
    all_indicators = atlas_data["macro"] + atlas_data["micro"]

    for indicator in all_indicators:
        indicator_id = indicator["id"]
        
        # Skip indicators that are PURELY MANUAL (GEOPOLITICAL) or COMPOSITES (FISCAL_RISK)
        # SNAP_BENEFITS must be fetched here as it is a dependency for FISCAL_RISK
        if indicator_id in ["GEOPOLITICAL", "FISCAL_RISK"]:
            print(f"Skipped: {indicator_id} is a manual/calculated input.")
        else:
            # Fetch the raw value using the appropriate API/FRED/YFinance logic
            indicator["value"] = fetch_indicator_data(indicator["id"])
            
    print("Data fetching complete. Starting scoring process.")

    # 4. RUN MAIN PROCESS (Scoring, Narrative, and Saving)
    try:
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
        import traceback
        print(traceback.format_exc())


if __name__ == "__main__":
    main()