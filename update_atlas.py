import json
import datetime
import random 
import requests
import os 
import pandas as pd # NEW: For reading the FINRA Excel file
from fredapi import Fred # NEW: For fetching FRED data
import yfinance as yf

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
    
    # 3. FRED SERIES IDS (The four successful series + five new for Liquidity/CDS/Delinquencies)
    "FRED_3YR_ID": "DGS3",
    "FRED_30YR_ID": "DGS30",
    "FRED_10YR_ID": "DGS10",  
    "FRED_HYOAS_ID": "BAMLH0A0HYM2", 
    "FRED_SOFR_3M_ID": "TB3MS",      # <-- NEW for SOFR/OIS Spread
    "FRED_EFFR_ID": "EFFR",             # <-- NEW for SOFR/OIS Spread
    "FRED_WALCL_ID": "WALCL",           # <-- NEW for Net Liquidity
    "FRED_WTREGEN_ID": "WTREGEN",       # <-- NEW for Net Liquidity
    "FRED_RRPONTSYD_ID": "RRPONTSYD",   # <-- NEW for Net Liquidity
    "FRED_BANK_CDS_ID": "AAA", # <-- Financial Index OAS (Proxy for Bank CDS)
    "FRED_CONSUMER_DELINQ_ID": "DRCCLACBS", # <-- Delinquency Rate on Credit Card Loans (Proxy)
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
    Sources: SOFR3MAD and EFFR. Result is in Basis Points.
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


# --- 1. DATA FETCHING AND PARSING FUNCTIONS (UPDATED FOR FALLBACK) ---

def fetch_indicator_data(indicator_id):
    """
    Fetches the latest data for all indicators, routing to FRED, new live functions, 
    or external APIs, and returns "N/A" for unautomated indicators.
    """
    
    # Define a safe fallback value for FRED series (e.g., median of their risk band)
    FRED_FALLBACK_VALUE = {
        "3Y_YIELD": 3.50, "30Y_YIELD": 4.25, "10Y_YIELD": 4.30, "HY_OAS": 380.0,
        # Fallbacks for the new calculated FRED indicators
        "TREASURY_LIQUIDITY": 100.0,
        "SOFR_OIS": 25.0,
        "BANK_CDS": 85.0, # Existing new fallback
        "CONSUMER_DELINQUENCIES": 2.2, # <-- NEW Fallback (typical 2-3% range)
    }

    # --- FRED API CALLS (For Yields and HY_OAS) ---
    fred_series_map = {
        "3Y_YIELD": API_CONFIG["FRED_3YR_ID"], 
        "30Y_YIELD": API_CONFIG["FRED_30YR_ID"],
        "10Y_YIELD": API_CONFIG["FRED_10YR_ID"], 
        "HY_OAS": API_CONFIG["FRED_HYOAS_ID"],
        "BANK_CDS": API_CONFIG["FRED_BANK_CDS_ID"], # Existing new map
        "CONSUMER_DELINQUENCIES": API_CONFIG["FRED_CONSUMER_DELINQ_ID"], # <-- NEW MAP
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
            
    # --- LIVE CALCULATED INDICATORS (NEW) ---
    
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

    # --- EXTERNAL API CALLS (Remaining) ---
    
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
    
    # --- UNIMPLEMENTED PLACEHOLDERS (Return "N/A") ---
    
    elif indicator_id in ["EARNINGS_REVISION", "BANK_CDS", "CONSUMER_DELINQUENCIES"]:
        return "N/A" # Unimplemented APIs return N/A
    
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

    return float(global_quote.get("05. price"))

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

    # 1. PLACEHOLDER CHECK - This block should ideally no longer be hit for automated indicators
    if endpoint.startswith("YOUR_") or api_key.startswith("YOUR_"):
        print(f"Placeholder: API endpoint or key for {indicator_id} is not configured. Returning fallback value {fallback_value}.")
        return fallback_value
    
    # --- YFINANCE LOGIC (VIX, Gold, SPX, ASX, SMALL_LARGE_RATIO, WTI_CRUDE, AUDUSD) ---
    
    if indicator_id in ["VIX", "GOLD_PRICE", "SPX_INDEX", "ASX_200", 
                        "SMALL_LARGE_RATIO", "WTI_CRUDE", "AUDUSD"]:
        try:
            if indicator_id not in ["SMALL_LARGE_RATIO"]:
                symbol_map = {
                    "VIX": "^VIX", "GOLD_PRICE": "GLD", "SPX_INDEX": "^GSPC",
                    "ASX_200": "^AXJO", "WTI_CRUDE": "USO", "AUDUSD": "AUDUSD=X"       
                }
                symbol = symbol_map[indicator_id]
                value = _fetch_yfinance_quote(symbol)
                
                formatting = "{:.4f}" if indicator_id in ["AUDUSD"] else "{:.2f}"
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
            
    if indicator_id in ["EURUSD"]: 
        try:
            av_value = _fetch_alpha_vantage_quote("EURUSD", api_key, endpoint)
            formatting = "{:.4f}"
            print(f"Success: Fetched {indicator_id} ({formatting.format(av_value)}) from Alpha Vantage.")
            return av_value 
            
        except Exception as e:
            print(f"{indicator_id} API Error: Data fetch failed: {e}. Returning fallback value {fallback_value}.")
            return fallback_value
            
    # Final Catch-All (Should not be reached if fetch_indicator_data is correct)
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
        "TREASURY_LIQUIDITY": "https://fred.stlouisfed.org/series/WALCL", # Use the Fed Balance Sheet as the anchor
        "SOFR_OIS": "https://fred.stlouisfed.org/series/SOFR3MAD", # Use 3M SOFR as the anchor
    }
    
    POLYGON_SOURCES = {
        "PUT_CALL_RATIO": "https://polygon.io/docs/options/get_v2_aggs_ticker__tickervar__prev",
    }
    
    AV_SOURCES = {
        "EURUSD": "https://www.alphavantage.co/documentation/#currency-exchange",
    }
    
    CUSTOM_SOURCES = {
        "MARGIN_DEBT_YOY": FINRA_LINK,
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


# --- MAIN LOGIC EXECUTION ---

def run_update_process(atlas_data):
    """
    The main process that executes the scoring logic and data writing.
    """
    # 1. Update data sources (Source Links)
    macro_indicators = _update_indicator_sources(atlas_data["macro"])
    micro_indicators = _update_indicator_sources(atlas_data["micro"])
    
    # [ ... The rest of your scoring logic (Calculate Score, Assign Status, Generate Narrative) goes here ... ]
    # DUMMY SCORING/NARRATIVE GENERATION (Replace with your actual scoring logic)
    atlas_data["overall"]["status"] = "MONITOR"
    atlas_data["overall"]["score"] = 6.0
    atlas_data["overall"]["max_score"] = 10.0
    atlas_data["overall"]["comment"] = "Market risk remains low, but credit stress is emerging."
    atlas_data["overall"]["daily_narrative"] = f"Today's Atlas analysis, dated {atlas_data['overall']['date']}, shows continued stability across global equities, supported by low implied volatility (VIX at {atlas_data['macro'][0]['value']:.2f}).\n\nHowever, the recent dip in Gold and Crude prices suggests a soft patch in commodity demand, and the spread between the 3Y and 30Y Treasury yield continues to indicate long-term economic deceleration. We are actively monitoring the high-yield credit market for further deterioration."
    atlas_data["overall"]["composite_summary"] = "Overall risk posture is stable, but watch for credit signals."


    # 2. Archive the daily narrative (FOR INFINITE SCROLL)
    save_to_archive(atlas_data["overall"])

    # 3. Write main data file
    try:
        with open(OUTPUT_FILE, 'w') as f:
            json.dump(atlas_data, f, indent=4)
        print(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}] Atlas JSON successfully generated and written to {OUTPUT_FILE}")
    except Exception as e:
        print(f"Error: Failed to write {OUTPUT_FILE}: {e}")


if __name__ == "__main__":
    
    print(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Starting Atlas data generation.")

    # --- 2. INITIALIZE ATLAS DATA STRUCTURE ---
    # This structure must contain ALL 17 indicators.
    atlas_data = {
        "overall": {
            "date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
            "status": "N/A", "score": 0.0, "max_score": 0.0, "comment": "", 
            "composite_summary": "", "daily_narrative": "",
        },
        "macro": [
             {"id": "VIX", "name": "Implied Volatility (VIX)", "value": 0.0, "status": "N/A", "note": "", "action": "No change.", "source_link": ""},
             {"id": "GOLD_PRICE", "name": "Gold Price (GLD Proxy)", "value": 0.0, "status": "N/A", "note": "", "action": "No change.", "source_link": ""},
             {"id": "EURUSD", "name": "EUR/USD Exchange Rate", "value": 0.0, "status": "N/A", "note": "", "action": "No change.", "source_link": ""},
             {"id": "WTI_CRUDE", "name": "WTI Crude Oil (USO Proxy)", "value": 0.0, "status": "N/A", "note": "", "action": "No change.", "source_link": ""},
             {"id": "AUDUSD", "name": "AUD/USD Exchange Rate", "value": 0.0, "status": "N/A", "note": "", "action": "No change.", "source_link": ""},
             {"id": "3Y_YIELD", "name": "3-Year Treasury Yield", "value": 0.0, "status": "N/A", "note": "", "action": "No change.", "source_link": ""},
             {"id": "30Y_YIELD", "name": "30-Year Treasury Yield", "value": 0.0, "status": "N/A", "note": "", "action": "No change.", "source_link": ""},
             {"id": "10Y_YIELD", "name": "10-Year Treasury Yield", "value": 0.0, "status": "N/A", "note": "", "action": "No change.", "source_link": ""},
             {"id": "HY_OAS", "name": "High-Yield Option-Adjusted Spread", "value": 0.0, "status": "N/A", "note": "", "action": "No change.", "source_link": ""},
             {"id": "TREASURY_LIQUIDITY", "name": "Treasury Net Liquidity ($B)", "value": 0.0, "status": "N/A", "note": "", "action": "No change.", "source_link": ""},
        ],
        "micro": [
             {"id": "SPX_INDEX", "name": "S&P 500 Index Price", "value": 0.0, "status": "N/A", "note": "", "action": "No change.", "source_link": ""},
             {"id": "ASX_200", "name": "ASX 200 Index Price", "value": 0.0, "status": "N/A", "note": "", "action": "No change.", "source_link": ""},
             {"id": "SOFR_OIS", "name": "SOFR/OIS Spread (bps)", "value": 0.0, "status": "N/A", "note": "", "action": "No change.", "source_link": ""},
             {"id": "PUT_CALL_RATIO", "name": "Put/Call Ratio (Total CBOE)", "value": 0.0, "status": "N/A", "note": "", "action": "No change.", "source_link": ""},
             {"id": "SMALL_LARGE_RATIO", "name": "Small/Large Cap Ratio", "value": 0.0, "status": "N/A", "note": "", "action": "No change.", "source_link": ""},
             {"id": "EARNINGS_REVISION", "name": "Earnings Revision Momentum", "value": 0.0, "status": "N/A", "note": "", "action": "No change.", "source_link": ""},
             {"id": "MARGIN_DEBT_YOY", "name": "FINRA Margin Debt YoY (%)", "value": 0.0, "status": "N/A", "note": "", "action": "No change.", "source_link": ""},
             {"id": "BANK_CDS", "name": "Bank CDS Index Spread (bps)", "value": 0.0, "status": "N/A", "note": "", "action": "No change.", "source_link": ""},
             {"id": "CONSUMER_DELINQUENCIES", "name": "Consumer Loan Delinquency Rate (%)", "value": 0.0, "status": "N/A", "note": "", "action": "No change.", "source_link": ""},
        ],
        "actions": ["Rebalance cash allocation.", "Monitor credit markets closely."],
        "escalation_triggers": [],
        "short_insight": [{"text": "Global equity risk remains muted despite rising long-end yields."}],
    }
    
    # --- 3. SCORING AND PROCESSING (FETCH DATA) ---
    # Placeholder loop to fetch data and fill in values before running the main process:
    for category in ["macro", "micro"]:
        for indicator in atlas_data[category]:
            indicator["value"] = fetch_indicator_data(indicator["id"])
            
            # Placeholder for status and note (will be overwritten by your actual scoring logic)
            indicator["status"] = random.choice(["GREEN", "AMBER", "RED", "N/A"]) if indicator["value"] != "N/A" else "N/A"
            indicator["note"] = f"Test Note. Value: {indicator['value']}. Status: {indicator['status']}" 

    # --- 4. RUN MAIN PROCESS ---
    run_update_process(atlas_data)

# --- UTILITY FUNCTION FOR SCORING OUTPUT ---
# NOTE: This function must be defined before all score_ functions.
def generate_score_output(status, note, action, score, source_link):
    """Formats the output into a tuple (status, note, action, score, source_link) for clean function returns."""
    return status, note, action, score, source_link


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
        score = -2.0
        action = "Increase portfolio volatility hedges."
    elif value >= 18.0:
        status = "Amber"
        note = f"VIX is moderate at {value:.2f}. Volatility is starting to increase."
        score = -1.0
        action = "Monitor volatility trends closely."

    return generate_score_output(status, note, action, score, source_link)


def score_3yr_yield(value):
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


def score_10yr_yield(value):
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


def score_30yr_yield(value):
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


def score_gold(value):
    """Gold Price (GLD ETF Proxy) Scoring"""
    status = "Green"
    note = f"Gold (GLD) is stable at ${value:.2f}. Suggests manageable inflation/risk."
    action = "No change."
    score = 0.0
    source_link = "https://finance.yahoo.com/quote/GLD/"

    if value <= 180.0:
        status = "Red"
        note = f"Gold (GLD) has broken below key support at ${value:.2f}. Suggests persistent disinflation/low risk demand."
        score = -1.5
        action = "Re-assess inflation-hedging exposure."
    elif value <= 190.0:
        status = "Amber"
        note = f"Gold (GLD) is drifting lower at ${value:.2f}. Monitor for risk-off flows."
        score = -0.5
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
        score = -1.5
        action = "Increase USD cash reserves; reduce emerging market exposure."
    elif value <= 1.1000:
        status = "Amber"
        note = f"EUR/USD is below key support levels at {value:.4f}. Monitor for increasing global liquidity stress."
        score = -0.75
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
    source_link = "https://www.eia.gov/dnav/pet/hist/rwtc.htm"

    if value >= 90.0:
        status = "Red"
        note = f"WTI Crude at ${value:.2f}/bbl. Aggressively high price. Major inflation headwind and geopolitical risk signal."
        action = "Increase defensive exposure. Monitor supply lines closely."
        score = 1.0
    elif value >= 75.0:
        status = "Amber"
        note = f"WTI Crude at ${value:.2f}/bbl. Elevated price range, watch for breaks above $90/bbl."
        action = "Ensure portfolio is hedged against inflation risks."
        score = 0.5

    return generate_score_output(status, note, action, score, source_link)


def score_audusd(value):
    """AUDUSD Scoring - Measures global risk appetite and US Dollar strength."""
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
    """ICE BofA HY OAS Scoring - Measures credit risk and liquidity stress (Micro Indicator)."""
    status = "Green"
    note = f"HY OAS at {value:.0f} bps. Normal risk conditions."
    action = "No change."
    score = 0.0
    source_link = "https://fred.stlouisfed.org/series/BAMLH0A0HYM2"

    if value >= 400.0:
        status = "Red"
        note = f"HY OAS at {value:.0f} bps. Credit stress is evident; market liquidity is impaired."
        action = "HY OAS ≥ 400 bps → aggressively favour cash and short-term US Treasuries."
        score = 1.0
    elif value >= 350.0:
        status = "Amber"
        note = f"HY OAS at {value:.0f} bps. Elevated spread, watch carefully for sustained moves above 400 bps."
        action = "Monitor HY OAS closely."
        score = 0.5

    return generate_score_output(status, note, action, score, source_link)


def score_spx(value):
    """S&P 500 Scoring - Measures US Equity Risk and General Market Sentiment (Micro Indicator)."""
    status = "Green"
    note = f"S&P 500 Index at {value:,.0f}. Trading near highs, risk-on sentiment prevailing."
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


def score_asx200(value):
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
        note = f"ASX 200 Index at {value:,.0f}. Moderate pullback from highs. Australian equity risk is elevated."
        action = "Avoid adding new AU equity exposure. Monitor commodity prices (Iron Ore/Copper)."
        score = 0.5

    return generate_score_output(status, note, action, score, source_link)


def score_put_call_ratio(value):
    """Put/Call ratio (CBOE) Scoring (Micro Indicator)."""
    status = "Amber"
    note = f"P/C ratio at {value:.2f} (hedging bias)."
    action = "Monitor closely."
    score = 0.5
    source_link = "https://www.cboe.com/us/options/market_statistics/daily/"

    if value >= 1.2:
        status = "Red"
        note = f"P/C ratio at {value:.2f}. Extreme hedging and fear (Panic). Long-term contrarian signal."
        action = "Tactically use extreme fear as a potential (short-term) contrarian entry signal."
        score = 1.0
    elif value <= 0.7:
        status = "Green"
        note = f"P/C ratio at {value:.2f}. Extreme complacency; low hedging activity. Long-term risk signal."
        action = "Extreme complacency is a long-term risk signal; maintain protective hedges."
        score = 0.0
    # 0.7 < value < 1.2 is Amber (Normal or hedging bias)

    return generate_score_output(status, note, action, score, source_link)


def score_small_large_ratio(value):
    """Small-cap / Large-cap ratio Scoring (Micro Indicator)."""
    status = "Red"
    note = f"Ratio at {value:.2f} — small-caps underperforming. Internals fragile."
    action = "Avoid growth stocks."
    score = 1.0
    source_link = ""

    if value >= 0.45:
        status = "Green"
        note = f"Ratio at {value:.2f}. Small-caps performing well; strong market internals."
        action = "No change."
        score = 0.0
    elif value >= 0.40:
        status = "Amber"
        note = f"Ratio at {value:.2f}. Small-caps under pressure; monitor market breadth."
        action = "Monitor closely for breaks below 0.40."
        score = 0.5
    # value < 0.40 is Red

    return generate_score_output(status, note, action, score, source_link)


def score_sofr_ois(value):
    """SOFR-OIS Spread Scoring - Measures US funding stress (Micro Indicator)."""
    
    # Initialize defaults
    status = "Green"
    note = "Funding markets are calm."
    action = "No change."
    score = 0.0
    source_link = "https://fred.stlouisfed.org/series/OISSOFR"
    
    # Handle string inputs
    if isinstance(value, str):
        if value.upper() == 'N/A':
            return generate_score_output("N/A", "Data N/A: SOFR-OIS Spread requires external API.", "Cannot score due to missing data.", 0.0, source_link)
        try:
            value = float(value)
        except ValueError:
            return generate_score_output("Error", "Error: SOFR-OIS value could not be converted to number.", "Cannot score due to data error.", 0.0, "")

    # Scoring Logic for numeric values
    if isinstance(value, float):
        note = f"SOFR-OIS spread at {value:.1f} bps. Funding markets are calm."
        
        if value >= 40.0:
            status = "Red"
            note = f"SOFR-OIS spread at {value:.1f} bps. Elevated funding market stress. Indicates acute counterparty risk / liquidity fear."
            score = 1.0
            action = "Monitor funding markets closely."
        elif value >= 25.0:
            status = "Amber"
            note = f"SOFR-OIS spread at {value:.1f} bps. Spread widening; caution warranted in short-term funding markets."
            score = 0.5
            action = "Monitor funding markets closely."

    return generate_score_output(status, note, action, score, source_link)


def score_treasury_liquidity(value):
    """US Treasury liquidity (Dealer/ADTV) Scoring (Macro Indicator)."""
    
    # Initialize defaults
    status = "Green"
    note = "Dealer ADTV: Market functioning."
    action = "No change."
    score = 0.0
    source_link = ""
    
    # Handle string inputs
    if isinstance(value, str):
        if value.upper() == 'N/A':
            return generate_score_output("N/A", "Data N/A: Treasury liquidity data requires external API.", "Cannot score due to missing data.", 0.0, source_link)
        try:
            value = float(value)
        except ValueError:
            return generate_score_output("Error", "Error: Treasury liquidity value could not be converted to number.", "Cannot score due to data error.", 0.0, "")

    # Scoring Logic for numeric values
    if isinstance(value, float):
        note = f"Dealer ADTV at ${value:.1f}B. Market functioning."
        
        if value <= 80.0:
            status = "Red"
            note = f"Dealer ADTV at ${value:.1f}B. Liquidity strain is evident; dealer capacity flagged."
            score = 1.0
            action = "Increase cash weighting and avoid complex fixed income trades."
        elif value <= 95.0:
            status = "Amber"
            note = f"Dealer ADTV at ${value:.1f}B. Liquidity is tightening; monitor trade volumes closely."
            score = 0.5
            action = "Monitor trade volumes closely."

    return generate_score_output(status, note, action, score, source_link)


def score_earnings_revision(value):
    """Earnings-revision breadth Scoring (Micro Indicator)."""
    
    # Initialize defaults
    status = "Amber"
    note = "Earnings weakening."
    action = "Monitor earnings forecasts closely."
    score = 0.5
    source_link = ""
    
    # Handle string inputs
    if isinstance(value, str):
        if value.upper() == 'N/A':
            return generate_score_output("N/A", "Data N/A: Earnings revision data requires external API.", "Cannot score due to missing data.", 0.0, source_link)
        try:
            value = float(value)
        except ValueError:
            return generate_score_output("Error", "Error: Earnings revision value could not be converted to number.", "Cannot score due to data error.", 0.0, "")

    # Scoring Logic for numeric values
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


def score_leverage_yoy(value):
    """Margin Debt YoY Scoring (Macro Indicator)."""
    
    # Initialize defaults
    status = "Amber"
    note = "High leverage is a risk."
    action = "Monitor closely for extreme values."
    score = 0.5
    source_link = ""
    
    # Handle string inputs
    if isinstance(value, str):
        if value.upper() == 'N/A':
            return generate_score_output("N/A", "Data N/A: Margin Debt YoY requires external data source.", "Cannot score due to missing data.", 0.0, source_link)
        try:
            value = float(value)
        except ValueError:
            return generate_score_output("Error", "Error: Margin Debt value could not be converted to number.", "Cannot score due to data error.", 0.0, "")

    # Scoring Logic for numeric values
    if isinstance(value, float):
        note = f"Margin Debt YoY at {value:.1f}%. High leverage is a risk."
        
        if value >= 10.0:
            status = "Red"
            note = f"Margin Debt YoY at {value:.1f}%. Extreme leverage growth. Implies high liquidation risk."
            score = 1.0
            action = "Increase short hedges; prepare for structural equity risk."
        elif value <= -5.0:
            status = "Green"
            note = f"Margin Debt YoY at {value:.1f}%. Leverage is being reduced. Reduces systemic liquidation risk."
            score = 0.0
            action = "No change."

    return generate_score_output(status, note, action, score, source_link)


def score_bank_cds(value):
    """Bank CDS Index Spread Scoring - Measures banking sector systemic risk."""
    
    # Initialize defaults
    status = "Green"
    note = "Low implied banking risk."
    action = "No change."
    score = 0.0
    source_link = "https://www.google.com/finance/quote/SX7E:INDEX?window=5Y"
    
    # Handle string inputs
    if isinstance(value, str):
        if value.upper() == 'N/A':
            return generate_score_output("N/A", "Data N/A: Bank CDS data requires external API.", "Cannot score due to missing data.", 0.0, source_link)
        try:
            value = float(value)
        except ValueError:
            return generate_score_output("Error", "Error: Bank CDS value could not be converted to number.", "Cannot score due to data error.", 0.0, "")
            
    # Scoring Logic for numeric values
    if isinstance(value, float):
        note = f"Bank CDS Index at {value:.0f} bps. Low implied banking risk."
        
        # Using the thresholds from our last correct step: 100/150 bps
        if value >= 150.0:
            status = "Red"
            note = f"Bank CDS Index at {value:.0f} bps. High implied banking risk. Indicates significant counterparty fear."
            score = -2.0
            action = "Aggressively reduce financial sector exposure and monitor interbank lending markets."
        elif value >= 100.0:
            status = "Amber"
            note = f"Bank CDS Index at {value:.0f} bps. Spreads are widening, caution warranted in banking exposure."
            score = -1.0
            action = "Monitor spreads closely; avoid adding new financial exposure."

    return generate_score_output(status, note, action, score, source_link)


def score_consumer_delinquencies(value):
    """
    Consumer Loan Delinquency Rate Scoring (using Credit Card Delinquency Rate as a FRED proxy).
    Measures household financial stress/credit quality.
    """
    
    source_link = "https://fred.stlouisfed.org/series/DRCCLACBS"
    
    # Handle N/A or Error
    if isinstance(value, (str, type(None))):
        return generate_score_output("N/A", "Data N/A: Consumer Delinquency data unavailable.", "Cannot score.", 0.0, source_link)

    # Initialize defaults
    status = "Green"
    note = f"Delinquency Rate at {value:.1f}%. Stable household credit quality."
    action = "No change."
    score = 0.0
    
    # Thresholds are based on the historical stress for credit card delinquency (using pre-COVID norms):
    if value >= 3.8:
        status = "Red"
        note = f"Delinquency Rate at {value:.1f}%. Aggressively high rate. Indicates significant household stress and consumer spending risk."
        score = 2.0
        action = "Aggressively reduce exposure to consumer discretionary and financial stocks with high unsecured loan exposure."
    elif value >= 2.8:
        status = "Amber"
        note = f"Delinquency Rate at {value:.1f}%. Rate is rising. Caution warranted for banks and consumer sectors."
        score = 1.0
        action = "Monitor household debt metrics closely; prefer defensive consumer sectors."

    return generate_score_output(status, note, action, score, source_link)

    # --- Scoring Logic for numeric values ---
    status = "Green"
    note = f"~{value:.1f}% — household delinquencies not yet critical."
    action = "Current level is low; no immediate action required."
    score = 0.0
    source_link = "" # FIX: Set source_link to empty string

    if value >= 3.0:
        status = "Red"
        note = f"~{value:.1f}% — household stress is acute. Significant pressure on consumer-facing businesses."
        action = "Avoid cyclical consumer stocks and local businesses dependent on household spending."
        score = 1.0 
    elif value >= 2.5:
        status = "Amber"
        note = f"~{value:.1f}% — delinquencies are rising; watch for acceleration towards 3.0%."
        action = "Monitor consumer credit quality closely."
        score = 0.5
    # value < 2.5 is Green
        
    return {
        "name": "Consumer delinquencies (30-day)", 
        "value": f"{value:.2f}%", # ADDED: Missing value field
        "status": status, 
        "note": note, 
        "source_link": source_link, 
        "action": action, 
        "score_value": score
        # Note: If your other scoring functions return 'grade' and 'color', you should add them here too.
    }
def score_geopolitical(value):
    """NEW: Geopolitical (China/Russia/region) Scoring (Micro Indicator)."""
    # This is a manual/qualitative score, we use a simple placeholder logic for demonstration
    
    # Placeholder: 0=Green, 0.5=Amber, 1.0=Red
    manual_score = value # Pass in 0, 0.5, or 1.0 based on manual assessment
    
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
        
    return {"name": "Geopolitical (China/Russia/region)", "value": value, "status": status, "note": note, "source_link": "", "action": action, "score_value": score} # FIX: Set source_link to empty string

def generate_narrative(score, overall_status, top_triggers, MAX_SCORE):
    """
    Generates a short summary and the full daily narrative based on the final score.
    """
    date_str = datetime.datetime.now().strftime("%A, %B %d, %Y")
    
    # Ensure all paths assign a value to narrative_summary and full_narrative

    if score >= 12.0: # FULL-STORM
        narrative_summary = f"Atlas remains at **FULL-STORM** risk. This is a critical liquidity posture driven by extreme VIX, credit spreads, and ongoing fiscal uncertainty. The primary mandate is maximum capital preservation and liquidity."
        full_narrative = (
            f"**Daily Atlas Analysis: FULL-STORM ({score:.1f}/{MAX_SCORE:.1f}) | {date_str}**\n\n"
            "The system is under maximum stress. (ADD DETAIL HERE)"
        )
    elif score >= 5.0: # ELEVATED RISK (MODERATE RISK based on your original comment)
        # This is the path your current 5.5 score should take
        narrative_summary = f"**{overall_status}** remains in place. Key volatility and FX triggers are active, warranting caution. Maintain defensive positioning and monitor micro-indicators for stabilization."
        full_narrative = (
            f"**Daily Atlas Analysis: {overall_status} ({score:.1f}/{MAX_SCORE:.1f}) | {date_str}**\n\n"
            "The risk environment is elevated but contained. While the majority of triggers are in the 'Amber' band, the sustained VIX and AUDUSD weakness suggest a tentative global risk appetite. (ADD DETAIL HERE)"
        )
    elif score >= 2.0: # CAUTIONARY RISK
        narrative_summary = f"**CAUTIONARY RISK** is active. Monitor key macro indicators like inflation and bond yields. Tactical hedges may be prudent."
        full_narrative = (
            f"**Daily Atlas Analysis: CAUTIONARY RISK ({score:.1f}/{MAX_SCORE:.1f}) | {date_str}**\n\n"
            "A mixed environment. Macro risk indicators are benign, but micro internals show some weakness. (ADD DETAIL HERE)"
        )
    else: # GREEN / LOW RISK (Default fallback)
        narrative_summary = "**LOW RISK** environment. Conditions favor pro-cyclical positioning. Maintain vigilance on core inflation data."
        full_narrative = (
            f"**Daily Atlas Analysis: LOW RISK ({score:.1f}/{MAX_SCORE:.1f}) | {date_str}**\n\n"
            "All core triggers are green. Market momentum is strong and volatility is low. (ADD DETAIL HERE)"
        )
        
    return narrative_summary, full_narrative

# --- 3. COMPILATION AND OVERALL SCORING (FINAL LOGIC) ---

def get_all_indicators():
    """Fetches and scores all Macro and Micro indicators, and compiles the final Atlas JSON."""
    
    # --- 1. Fetch Raw Data ---
    # Existing Macro
    raw_vix = fetch_indicator_data("VIX")
    raw_3yr = fetch_indicator_data("3Y_YIELD")
    raw_10yr = fetch_indicator_data("10Y_YIELD")
    raw_30yr = fetch_indicator_data("30Y_YIELD")
    raw_gold = fetch_indicator_data("GOLD_PRICE")
    raw_eurusd = fetch_indicator_data("EURUSD")
    raw_wti = fetch_indicator_data("WTI_CRUDE") 
    raw_audusd = fetch_indicator_data("AUDUSD")
    # NEW Macro
    raw_treasury_liquidity = fetch_indicator_data("TREASURY_LIQUIDITY") 
    
    # Existing Micro
    raw_spx = fetch_indicator_data("SPX_INDEX") 
    raw_hy_oas = fetch_indicator_data("HY_OAS")
    raw_asx200 = fetch_indicator_data("ASX_200")
    raw_sofr_ois = fetch_indicator_data("SOFR_OIS") 
    # NEW Micro
    raw_put_call = fetch_indicator_data("PUT_CALL_RATIO")
    raw_small_large = fetch_indicator_data("SMALL_LARGE_RATIO")
    raw_earnings = fetch_indicator_data("EARNINGS_REVISION")
    raw_leverage = fetch_indicator_data("MARGIN_DEBT_YOY")
    raw_bank_cds = fetch_indicator_data("BANK_CDS")
    raw_consumer_del = fetch_indicator_data("CONSUMER_DELINQUENCIES")
    # Manual Qualitative Score for Geopolitical (Example: 0.5 for Amber)
    raw_geopolitical_score = 0.5 
    
    # --- 2. Score Indicators ---
    # Existing Macro Scores
    vix_result = score_vix(raw_vix)
    yield_3yr_result = score_3yr_yield(raw_3yr)
    yield_10yr_result = score_10yr_yield(raw_10yr)
    yield_30yr_result = score_30yr_yield(raw_30yr)
    gold_result = score_gold(raw_gold)
    eurusd_result = score_eurusd(raw_eurusd)
    wti_result = score_wti_crude(raw_wti) 
    audusd_result = score_audusd(raw_audusd)
    # NEW Macro Score
    treasury_liquidity_result = score_treasury_liquidity(raw_treasury_liquidity)
    
    # Existing Micro Scores
    spx_result = score_spx(raw_spx) 
    hy_oas_result = score_hy_oas(raw_hy_oas)
    asx200_result = score_asx200(raw_asx200)
    sofr_ois_result = score_sofr_ois(raw_sofr_ois) 
    # NEW Micro Scores
    put_call_result = score_put_call_ratio(raw_put_call)
    small_large_result = score_small_large_ratio(raw_small_large)
    earnings_result = score_earnings_revision(raw_earnings)
    leverage_result = score_leverage_yoy(raw_leverage)
    bank_cds_result = score_bank_cds(raw_bank_cds)
    consumer_del_result = score_consumer_delinquencies(raw_consumer_del)
    geopolitical_result = score_geopolitical(raw_geopolitical_score)
    
    # Placeholder for a non-data-driven (manual) indicator
    shutdown_result = {
        "name": "US Government shutdown / fiscal risk",
        "status": "Red",
        "note": "Shutdown continuing into its 29th day; CBO estimates material GDP cost.",
        "source_link": "https://www.cbo.gov/",
        "action": "If >30 days or material funding breakdown → escalate to full storm (operational/fiscal shock).",
        "score_value": 1.0
    }
    
    # --- 3. Compile Results and Scores ---
    
    macro_list = [
        vix_result, 
        yield_3yr_result, 
        yield_10yr_result, 
        yield_30yr_result, 
        gold_result,
        eurusd_result, 
        wti_result, 
        audusd_result, 
        shutdown_result,
        treasury_liquidity_result, # NEW Macro Indicator
        # Total Macro Indicators: 10
    ]
    
    micro_list = [
        hy_oas_result,
        sofr_ois_result, 
        put_call_result, # NEW
        small_large_result, # NEW
        earnings_result, # NEW
        leverage_result, # NEW
        bank_cds_result, # NEW
        consumer_del_result, # NEW
        geopolitical_result, # NEW
        spx_result, 
        asx200_result, 
        # Total Micro Indicators: 11
    ]
    
    total_macro_score = sum(r.get("score_value", 0) for r in macro_list)
    total_micro_score = sum(r.get("score_value", 0) for r in micro_list)
    
    # Max score calculation: 10 Macro (max 10.0) + (11 Micro * 0.5) (max 5.5) = 15.5
    composite_score = total_macro_score + (total_micro_score * 0.5) 
    MAX_SCORE = 15.5 # Updated Max Score
    
    # Determine Overall Status based on the NEW thresholds (Adjusted for higher Max Score)
    score = composite_score 
    if score > 12.0: # ADJUSTED for new MAX_SCORE
        overall_status = "FULL-STORM"
        comment = "EXTREME RISK. Multiple systemic and funding triggers active. Maintain maximum defensive posture."
    elif score > 8.0: # ADJUSTED for new MAX_SCORE
        overall_status = "SEVERE RISK"
        comment = "HIGH RISK. Significant Macro and/or Micro triggers active. Aggressively increase liquidity and hedges (Storm Posture)."
    elif score > 4.0: # ADJUSTED for new MAX_SCORE
        overall_status = "ELEVATED RISK"
        comment = "MODERATE RISK. Core volatility/duration triggers active. Proceed with caution; maintain protective hedges."
    else: # Score <= 4.0
        overall_status = "MONITOR (GREEN)"
        comment = "LOW RISK. Only minor triggers active. Favour moderate risk-on positioning."
    
    # Get top 3 red/amber triggers for narrative
    all_triggers = sorted(macro_list + micro_list, key=lambda x: x['score_value'], reverse=True)
    top_triggers = [t['name'] for t in all_triggers if t['score_value'] >= 0.5][:3]
    
    # 4. Generate Narrative
    narrative_summary, full_narrative = generate_narrative(composite_score, overall_status, top_triggers, MAX_SCORE)


    # Construct the final JSON dictionary (Updated with narrative fields)
    data = {
        "overall": {
            "date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
            "status": overall_status,
            "score": composite_score, 
            "max_score": MAX_SCORE,
            "comment": comment,
            "composite_summary": f"Composite effective triggers ≈ {composite_score:.1f} / {MAX_SCORE:.1f} → {overall_status} posture confirmed.",
            "narrative_summary": narrative_summary, # NEW FIELD
            "daily_narrative": full_narrative # NEW FIELD
        },
        "macro": [
            {k: v for k, v in item.items() if k != 'score_value'} for item in macro_list
        ],
        "micro": [
            {k: v for k, v in item.items() if k != 'score_value'} for item in micro_list
        ],
        "actions": [
            "Hold Storm posture now. Maintain defensive allocations (cash + short/floating duration + low-vol) — do not de-risk into equities.",
            "Liquidity: keep ≥30% of capital liquid/unlocked for opportunistic buys or to meet operational calls.",
            "Duration: avoid adding intermediate/long locks in fixed income; favour floating-rate notes and short ladders in US & AU sleeves.",
            "Gold / safe-assets: maintain or modestly increase (5–10%) in liquid form (ETF/approved vehicles) — central-bank buying validates a tactical hedge.",
            "Hedging: if you hold concentrated equity positions, buy protective puts sized to cover a 10–15% drawdown while VIX remains elevated."
        ],
        "escalation_triggers": [
            {"name": "VIX", "note": ">25 sustained 3 trading days."},
            {"name": "HY OAS", "note": ">400 bps."},
            {"name": "US shutdown", "note": ">30 days or material funding default."},
            {"name": "ASX close", "note": "<8,000."},
            {"name": "SOFR–OIS", "note": ">40 bps sustained (funding stress)."} 
        ],
        "short_insight": [
            {"text": "A defensive posture is correct — keep discipline, hold dry powder, and step in methodically only when both macro and micro relief conditions align."},
            {"text": "Liquidity is functioning, which is important — hedges and tactical buys are feasible. But functioning markets are not the same as safety; price risk is high."}
        ]
    }
    
    # 5. Write to JSON file
    try:
        with open(OUTPUT_FILE, 'w') as f:
            json.dump(data, f, indent=4)
        print(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}] Atlas JSON successfully generated and written to {OUTPUT_FILE}")
    except Exception as e:
        print(f"Error writing JSON file: {e}")


# --- MAIN EXECUTION (Correct Final Block) ---
if __name__ == "__main__":
    # ... Your finalized atlas_data initialization structure ...
    # ... Your fetching loop that sets indicator["value"] ...
    # ... A single call to the correct processor:
    run_update_process(atlas_data)