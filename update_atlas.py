import json
import datetime
import random 
import requests
import os 
import pandas as pd 
from fredapi import Fred 
import yfinance as yf
# Assuming you use a separate library for narrative generation (like Google GenAI)
# from google import genai 
# from google.genai import types 


# --- CONFIGURATION ---

# 1. Output File Paths
OUTPUT_FILE = "data/atlas-latest.json" 
ARCHIVE_FILE = "data/atlas-archive.json" 

# 2. API Keys and Endpoints (Placeholder structure)
# WARNING: Store real keys securely (e.g., environment variables)
API_CONFIG = {
    # 1. FRED KEY & ENDPOINT
    "FRED_API_KEY": "YOUR_FRED_KEY_HERE", # <--- **UPDATE THIS KEY**
    "FRED_ENDPOINT": "https://api.stlouisfed.org/fred/series/observations",
  
    # 2. FRED SERIES IDS
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
    # SNAP Benefits - Total Participants in SNAP (WPTNS is a common proxy)
    "FRED_SNAP_ID": "WPTNS", 
}

# Initialize FRED client
FRED_API_KEY = API_CONFIG.get("FRED_API_KEY")
if FRED_API_KEY and FRED_API_KEY != "YOUR_FRED_KEY_HERE":
    fred = Fred(api_key=FRED_API_KEY)
else:
    fred = None 
    print("Warning: FRED client not initialized. FRED-based indicators will return fallbacks.")


# --- HELPER FUNCTIONS ---

def _fetch_fred_data_two_points(fred_id, fred_api_key):
    """Fetches the last two observation values for a given FRED series: [Previous, Current]."""
    try:
        fred = Fred(api_key=fred_api_key)
        # Request data monthly/quarterly as needed for the series ID
        series_data = fred.get_series(fred_id, observation_start=(datetime.datetime.now() - datetime.timedelta(days=365)).strftime('%Y-%m-%d'))
        
        if series_data is None or series_data.empty or len(series_data) < 2:
            print(f"Warning: FRED series {fred_id} returned less than 2 data points. Defaulting to [0.0, 0.0].")
            return [0.0, 0.0]
           
        # Get the last two values as a list: [Previous Period, Current Period]
        last_two_values = series_data.dropna().tail(2).values.tolist()
        
        # Ensure float conversion and return 
        if len(last_two_values) < 2:
            return [0.0, 0.0]
        
        return [float(last_two_values[0]), float(last_two_values[1])]
        
    except Exception as e:
        print(f"Error fetching FRED data for {fred_id}: {e}")
        return [0.0, 0.0]

# --- INDICATOR DATA FETCHING FUNCTIONS (LIVE) ---

def get_treasury_net_liquidity():
    """Calculates Treasury Net Liquidity: Fed Balance Sheet - (TGA + ON RRP). Result in Billions USD."""
    if not fred: return 0.0
    try:
        walcl = fred.get_series_latest_release(API_CONFIG["FRED_WALCL_ID"]).iloc[-1]
        wtregen = fred.get_series_latest_release(API_CONFIG["FRED_WTREGEN_ID"]).iloc[-1]
        rrpontsyd = fred.get_series_latest_release(API_CONFIG["FRED_RRPONTSYD_ID"]).iloc[-1]
        net_liquidity = walcl - (wtregen + rrpontsyd)
        return round(net_liquidity / 1000, 2)
    except Exception as e:
        print(f"FRED API Error for Net Liquidity: {e}")
        return 0.0 

def get_finra_margin_debt_yoy():
    """Fetches FINRA Margin Debt and calculates YOY change (percentage)."""
    FINRA_URL = "https://www.finra.org/sites/default/files/2021-03/margin-statistics.xlsx"
    try:
        df = pd.read_excel(FINRA_URL, sheet_name=0, header=1)
        df.columns = ['Date', 'Debit_Balance', 'Free_Credit_Cash', 'Free_Credit_Margin']
        df = df.dropna(subset=['Date', 'Debit_Balance']).sort_values(by='Date', ascending=False).reset_index(drop=True)
        if len(df) < 13: return 0.0
        current_debt = df['Debit_Balance'][0]
        previous_year_debt = df['Debit_Balance'][12]
        yoy_change = ((current_debt / previous_year_debt) - 1) * 100
        return round(yoy_change, 2)
    except Exception as e:
        print(f"FINRA Margin Debt Error: {e}")
        return 0.0 

def get_sofr_ois_spread():
    """Calculates the SOFR/EFFR Spread (proxy for SOFR OIS Spread) in Basis Points."""
    if not fred: return 0.0
    try:
        sofr_3m = fred.get_series_latest_release(API_CONFIG["FRED_SOFR_3M_ID"]).iloc[-1]
        effr = fred.get_series_latest_release(API_CONFIG["FRED_EFFR_ID"]).iloc[-1]
        spread = (sofr_3m - effr) * 100
        return round(spread, 2) 
    except Exception as e:
        print(f"FRED API Error for SOFR OIS Spread: {e}")
        return 0.0 

def _fetch_yfinance_quote(ticker):
    """Fetches the last close price for a given ticker."""
    try:
        data = yf.download(ticker, period="1d", interval="1d", progress=False)
        if data.empty:
            raise ValueError(f"No data returned for {ticker}")
        return data['Close'].iloc[-1].item()
    except Exception as e:
        print(f"YFinance Error for {ticker}: {e}")
        return 0.0 # Return 0.0 for failure

def fetch_external_data(endpoint_type, api_key_name, indicator_id, fallback):
    """Placeholder for external API calls like VIX, Gold, FX. Uses YFinance as a simple fallback."""
    
    TICKER_MAP = {
        "VIX": "^VIX", "GOLD_PRICE": "GLD", "EURUSD": "EURUSD=X", 
        "WTI_CRUDE": "CL=F", "AUDUSD": "AUDUSD=X", "SPX_INDEX": "^GSPC", 
        "ASX_200": "^AXJO"
    }
    
    if indicator_id == "PUT_CALL_RATIO":
        # Using a simple random value for a demo of external data, replace with Polygon/etc. fetch
        return round(random.uniform(0.7, 1.2), 2)
        
    elif indicator_id == "SMALL_LARGE_RATIO":
        # Calculated from YFinance
        large_cap = _fetch_yfinance_quote("^GSPC") # S&P 500
        small_cap = _fetch_yfinance_quote("^RUT") # Russell 2000
        if large_cap > 0 and small_cap > 0:
            return round(small_cap / large_cap, 4)
        return fallback

    elif indicator_id in TICKER_MAP:
        return _fetch_yfinance_quote(TICKER_MAP[indicator_id])

    return fallback


def fetch_indicator_data(indicator_id):
    """Routes fetching to FRED, new live functions, or external APIs."""
    
    FRED_FALLBACK_VALUE = { 
        "3Y_YIELD": 3.50, "30Y_YIELD": 4.25, "10Y_YIELD": 4.30, "HY_OAS": 380.0,
        "TREASURY_LIQUIDITY": 100.0, "SOFR_OIS": 25.0, "BANK_CDS": 85.0, 
        "CONSUMER_DELINQUENCIES": 2.2, 
    }

    # --- FRED API CALLS (Single-Point Fetch) ---
    fred_series_map = {
        "3Y_YIELD": API_CONFIG["FRED_3YR_ID"], "30Y_YIELD": API_CONFIG["FRED_30YR_ID"],
        "10Y_YIELD": API_CONFIG["FRED_10YR_ID"], "HY_OAS": API_CONFIG["FRED_HYOAS_ID"],
        "BANK_CDS": API_CONFIG["FRED_BANK_CDS_ID"], "CONSUMER_DELINQUENCIES": API_CONFIG["FRED_CONSUMER_DELINQ_ID"], 
    }

    if indicator_id in fred_series_map:
        series_id = fred_series_map[indicator_id]
        fallback = FRED_FALLBACK_VALUE.get(indicator_id, 0.0)
        
        try:
            params = {
                "series_id": series_id, "api_key": API_CONFIG["FRED_API_KEY"],
                "file_type": "json", "sort_order": "desc", "limit": 1
            }
            response = requests.get(API_CONFIG["FRED_ENDPOINT"], params=params)
            response.raise_for_status() 
            data = response.json()
            
            for obs in data.get("observations", []):
                if obs["value"] != ".": return float(obs["value"]) 
            
            print(f"FRED Warning: No valid data for {indicator_id}. Returning fallback {fallback}.")
            return fallback

        except requests.exceptions.RequestException as e:
            print(f"FRED Error fetching {indicator_id}: {e}. Returning fallback {fallback}.")
            return fallback

    # --- CUSTOM FRED API CALLS (Multi-Point Fetch) ---
    elif indicator_id == "SNAP_BENEFITS":
        fred_id = API_CONFIG.get("FRED_SNAP_ID", "WPTNS") 
        return _fetch_fred_data_two_points(fred_id, API_CONFIG["FRED_API_KEY"]) 
            
    # --- LIVE CALCULATED INDICATORS ---
    elif indicator_id == "TREASURY_LIQUIDITY":
        return get_treasury_net_liquidity()
    elif indicator_id == "SOFR_OIS": 
        return get_sofr_ois_spread()
    elif indicator_id == "MARGIN_DEBT_YOY": 
        return get_finra_margin_debt_yoy()

    # --- EXTERNAL/YFINANCE API CALLS ---
    elif indicator_id in ["VIX", "GOLD_PRICE", "EURUSD", "WTI_CRUDE", "AUDUSD", 
                          "SPX_INDEX", "ASX_200", "SMALL_LARGE_RATIO", "PUT_CALL_RATIO"]: 
        
        fallback_map = {
            "VIX": 22.0, "GOLD_PRICE": 2000.00, "EURUSD": 1.14, "WTI_CRUDE": 80.0, 
            "AUDUSD": 0.68, "SPX_INDEX": 4400.0, "ASX_200": 8600.0, "SMALL_LARGE_RATIO": 0.42,
            "PUT_CALL_RATIO": 0.9
        }
        return fetch_external_data("FX_ENDPOINT", "FX_API_KEY", indicator_id, fallback_map.get(indicator_id, 0.0))

    # --- UNIMPLEMENTED PLACEHOLDERS ---
    elif indicator_id == "EARNINGS_REVISION": 
        return "N/A" 
    
    return None 

# --- RISK SCORING LOGIC ---

# [Placeholder scoring functions defined here for completeness, e.g., score_vix, score_3y_yield, etc.]
def score_vix(value): return 0.0
def score_3y_yield(value): return 0.0
def score_10y_yield(value): return 0.0
def score_30y_yield(value): return 0.0
def score_gold_price(value): return 0.0
def score_eurusd(value): return 0.0
def score_wti_crude(value): return 0.0
def score_audusd(value): return 0.0
def score_hy_oas(value): return 0.0
def score_treasury_liquidity(value): return 0.0
def score_sofr_ois(value): return 0.0
def score_spx_index(value): return 0.0
def score_asx_200(value): return 0.0
def score_put_call_ratio(value): return 0.0
def score_small_large_ratio(value): return 0.0
def score_earnings_revision(value): return 0.0
def score_margin_debt_yoy(value): return 0.0
def score_bank_cds(value): return 0.0
def score_consumer_delinquencies(value): return 0.0
def score_geopolitical(value): return 0.0


def score_fiscal_risk(atlas_data):
    """Calculates the FISCAL_RISK score (Max 100) based on four factors."""
    
    # 1. Social Service Delivery (SNAP Deviation Score) - MAX 25 
    snap_values = next(
        (item['value'] for item in atlas_data['macro'] if item['id'] == 'SNAP_BENEFITS' and isinstance(item['value'], list)), 
        [0.0, 0.0] 
    ) 
    prev_month_snap = snap_values[0] 
    current_month_snap = snap_values[1]
    snap_score = 5 # Default: Low Risk
    
    if prev_month_snap > 0 and current_month_snap > 0:
        mom_change_percent = ((current_month_snap - prev_month_snap) / prev_month_snap) * 100
    else:
        mom_change_percent = 0
        snap_score = 25 if prev_month_snap == 0 and current_month_snap == 0 else 5
        
    if abs(mom_change_percent) >= 5.0: 
        snap_score = 25 
    elif abs(mom_change_percent) >= 2.5: 
        snap_score = 15
    else:
        snap_score = 5 

    # 2. Structural Integrity (Corruption Perception Index Placeholder) - MAX 25
    us_cpi = 69 
    corruption_score = max(0, min(25, (100 - us_cpi) / 4))

    # 3. Social Stress Proxy (VIX Index) - MAX 25 
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

    # 4. Data/Regulatory Confidence (Narrative Analysis Placeholder) - MAX 25
    reg_confidence_score = 10 
    
    # --- Compile Final Score ---
    total_fiscal_risk_score = (
        snap_score + corruption_score + civil_unrest_score + reg_confidence_score
    )
    
    # Store the breakdown in the metadata (optional, but good practice)
    if "meta" not in atlas_data: atlas_data["meta"] = {}
    atlas_data["meta"]["fiscal_breakdown"] = {
        "snap_score": snap_score,
        "corruption_score": round(corruption_score, 2),
        "civil_unrest_score": civil_unrest_score,
        "reg_confidence_score": reg_confidence_score
    }
    
    return round(total_fiscal_risk_score, 2)


# Map indicator IDs to their scoring functions
SCORING_FUNCTIONS = {
    "VIX": score_vix, "GOLD_PRICE": score_gold_price, "EURUSD": score_eurusd,
    "WTI_CRUDE": score_wti_crude, "AUDUSD": score_audusd, "3Y_YIELD": score_3y_yield,
    "30Y_YIELD": score_30y_yield, "10Y_YIELD": score_10y_yield, "HY_OAS": score_hy_oas,
    "TREASURY_LIQUIDITY": score_treasury_liquidity, "FISCAL_RISK": score_fiscal_risk,
    "SPX_INDEX": score_spx_index, "ASX_200": score_asx_200, "SOFR_OIS": score_sofr_ois,
    "PUT_CALL_RATIO": score_put_call_ratio, "SMALL_LARGE_RATIO": score_small_large_ratio,
    "EARNINGS_REVISION": score_earnings_revision, "MARGIN_DEBT_YOY": score_margin_debt_yoy,
    "BANK_CDS": score_bank_cds, "CONSUMER_DELINQUENCIES": score_consumer_delinquencies,
    "GEOPOLITICAL": score_geopolitical, "SNAP_BENEFITS": lambda x: 0.0 # Raw data, not scored
}


# --- MAIN PROCESSING FUNCTIONS ---

def run_update_process(atlas_data):
    """Executes the scoring and narrative generation stages."""
    
    # 1. Score all indicators
    all_indicators = atlas_data["macro"] + atlas_data["micro"]
    
    for indicator in all_indicators:
        indicator_id = indicator["id"]
        
        scoring_func = SCORING_FUNCTIONS.get(indicator_id)
        
        if scoring_func:
            # Special case for FISCAL_RISK: pass the whole data structure
            if indicator_id == "FISCAL_RISK":
                indicator["value"] = scoring_func(atlas_data) 
            # Otherwise, pass the raw value
            else:
                indicator["score_value"] = scoring_func(indicator.get("value"))
        
        # [ ... Logic for setting status, rating, action based on score_value is omitted ... ]

    # 2. Calculate overall score (Sum of all score_value fields)
    total_score = sum(item.get("score_value", 0) for item in all_indicators if item['id'] != 'FISCAL_RISK')
    
    # Update Overall Status
    atlas_data["overall"]["score"] = total_score
    atlas_data["overall"]["date"] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # [ ... Logic for generating narrative and overall status is omitted ... ]

    return atlas_data


# --- DATA TEMPLATE ---

# Simplified template ensuring FISCAL_RISK and SNAP_BENEFITS are present
INITIAL_ATLAS_DATA_TEMPLATE = {
    "overall": {"date": "", "status": "GREEN", "score": 0.0, "max_score": 10.0, "comment": ""},
    "macro": [
        {"id": "VIX", "name": "Implied Volatility (VIX)", "value": 0.0, "score_value": 0.0},
        {"id": "SNAP_BENEFITS", "name": "SNAP Benefits (MoM % Chg)", "value": 0.0, "score_value": 0.0},
        {"id": "TREASURY_LIQUIDITY", "name": "Treasury Net Liquidity ($B)", "value": 0.0, "score_value": 0.0},
        {"id": "FISCAL_RISK", "name": "Fiscal Risk (Shutdown/Debt)", "value": 0.0, "score_value": 0.0},
        {"id": "HY_OAS", "name": "HY OAS (Credit Stress)", "value": 0.0, "score_value": 0.0},
        {"id": "GOLD_PRICE", "name": "Gold Price (Proxy)", "value": 0.0, "score_value": 0.0},
        {"id": "10Y_YIELD", "name": "10-Year Yield", "value": 0.0, "score_value": 0.0},
        # Add the rest of your macro indicators here...
    ],
    "micro": [
        {"id": "SPX_INDEX", "name": "S&P 500 Index Price", "value": 0.0, "score_value": 0.0},
        {"id": "MARGIN_DEBT_YOY", "name": "Margin Debt YoY", "value": 0.0, "score_value": 0.0},
        {"id": "GEOPOLITICAL", "name": "Geopolitical Risk", "value": 0.0, "score_value": 0.0},
        # Add the rest of your micro indicators here...
    ]
}


# --- MAIN EXECUTION ---

def main():
    atlas_data = INITIAL_ATLAS_DATA_TEMPLATE 
    
    # 1. Archive the old data
    # [ ... Archive logic omitted for brevity ... ]

    # 2. Fetch Raw Data
    print("Fetching data from all accredited APIs...")
    
    all_indicators = atlas_data["macro"] + atlas_data["micro"]

    for indicator in all_indicators:
        indicator_id = indicator["id"]
        
        # --- FIX FOR NoneType ERROR ---
        # Skip indicators that are MANUALLY SET (GEOPOLITICAL) or CALCULATED LATER (FISCAL_RISK).
        if indicator_id in ["GEOPOLITICAL", "FISCAL_RISK"]:
            print(f"Skipped: {indicator_id} is a manual/calculated input.")
        else:
            # Fetch the raw value
            indicator["value"] = fetch_indicator_data(indicator["id"])
            
    print("Data fetching complete. Starting scoring process.")

    # 3. Run Main Process (Scoring, Narrative, and Saving)
    try:
        updated_atlas_data = run_update_process(atlas_data)
        
        # Save the Final Results to the main output file
        with open(OUTPUT_FILE, 'w') as f:
            json.dump(updated_atlas_data, f, indent=4) 
        print(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Success: Atlas JSON successfully generated and written to {OUTPUT_FILE}")

    except Exception as e:
        print(f"Critical Error during update process: {e}")


if __name__ == "__main__":
    main()