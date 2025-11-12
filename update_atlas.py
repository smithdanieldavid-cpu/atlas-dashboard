import re
import json
import datetime
import random 
import requests
import os 
import pandas as pd 
import yfinance as yf
from fredapi import Fred 
from google import genai 
from google.genai import types
from news_fetcher import fetch_news_sentiment 
# NOTE: Ensure the 'news_fetcher.py' file exists and contains the required function.
# NOTE: Ensure 'openpyxl' is installed for reading .xlsx files for Margin Debt.

# --- CONFIGURATION ---

# 1. Output File Path
OUTPUT_FILE = "data/atlas-latest.json" 
# Archive File Path for infinite scroll
ARCHIVE_FILE = "data/atlas-archive.json" 

# 2. Global Constants
MAX_SCORE = 25.0 # Total possible risk score for composite status

# --- CONSTANTS & PLACEHOLDER GLOBALS (Ensure these are defined near the top) ---
# Define the maximum score used for status mapping (adjust as necessary)
ATLAS_SCORE_STATUSES = {
    "FULL-STORM (EXTREME RISK)": (12.0, float("inf")),
    "SEVERE RISK (HIGH RISK)": (8.0, 12.0),
    "ELEVATED RISK (MODERATE RISK)": (4.0, 8.0),
    "MONITOR (LOW RISK)": (0.0, 4.0),
}


# --- UTILITY FUNCTIONS: Score Mappers ---

def map_score_to_status(score):
    """Maps a composite score to a risk status string."""
    # Uses the global ATLAS_SCORE_STATUSES
    for status, (lower, upper) in ATLAS_SCORE_STATUSES.items():
        if lower <= score < upper:
            return status
    return "UNKNOWN"

def map_score_to_comment(score):
    """Provides a brief comment based on the risk score."""
    status = map_score_to_status(score)
    if status == "SEVERE RISK":
        return "Extreme market fragility driven by systemic factors."
    elif status == "HIGH RISK":
        return "Aggressive risk-off posture; defensive allocation advised."
    elif status == "MEDIUM RISK":
        return "Caution warranted; mixed signals dominating market trends."
    else:
        return "Base case stability; monitor geopolitical and inflation risks."


# Initialize FRED client
FRED_API_KEY = os.environ.get("FRED_API_KEY")
if FRED_API_KEY:
    fred = Fred(api_key=FRED_API_KEY)
else:
    fred = None 
    print("Warning: FRED_API_KEY is missing. FRED-based indicators will return fallbacks.")


# FRED Series IDs
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


# --- UTILITY FUNCTIONS ---

def generate_score_output(status, note, action, score, source_link):
    """Formats the output into a dictionary for clean function returns."""
    return {
        "status": status, 
        "note": note, 
        "action": action,
        "score_value": score, 
        "source_link": source_link
    }

def _fetch_fred_data_two_points(series_id):
    """
    Helper function to fetch the two most recent data points for a FRED series.
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

def fetch_fx_data(ticker):
    """Fetches the latest data for an FX pair or commodity using yfinance."""
    try:
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

def _fetch_yfinance_quote(symbol):
    """Internal function to fetch the latest close price using yfinance."""
    ticker = yf.Ticker(symbol) 
    data = ticker.history(period="1d", interval="1d") 

    if data.empty:
        raise ValueError(f"yfinance returned no data for symbol {symbol}.")

    close_price = data['Close'].iloc[-1]
    
    return float(close_price)


# --- YFINANCE WRAPPER FUNCTIONS (Used by fetch_indicator_data) ---

def fetch_vix_index():
    """Fetches the latest VIX Index value using yfinance."""
    try:
        vix_data = yf.download('^VIX', period='1d', interval='1d', progress=False)
        if not vix_data.empty:
            vix_value = vix_data['Close'].iloc[-1].item()
            print(f"Success: Fetched VIX_INDEX ({vix_value:.2f}) from yfinance.")
            return vix_value
        print("Warning: VIX data is empty. Returning fallback.")
        return 18.0 # Fallback
    except Exception as e:
        print(f"Error fetching VIX: {e}. Returning fallback.")
        return 18.0 # Fallback

def fetch_gold_price():
    """Fetches the latest Gold Price (via GLD ETF) using yfinance."""
    try:
        gold_data = yf.download('GLD', period='1d', interval='1d', progress=False)
        if not gold_data.empty:
            gold_value = gold_data['Close'].iloc[-1].item()
            print(f"Success: Fetched GOLD_PRICE ({gold_value:.2f}) from yfinance.")
            return gold_value
        print("Warning: Gold price data is empty. Returning fallback.")
        return 200.00 # Fallback
    except Exception as e:
        print(f"Error fetching Gold Price: {e}. Returning fallback.")
        return 200.00 # Fallback

def fetch_spx_index():
    """Fetches the latest S&P 500 Index value using yfinance."""
    try:
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
        asx_data = yf.download('^AXJO', period='1d', interval='1d', progress=False)
        if not asx_data.empty:
            asx_value = asx_data['Close'].iloc[-1].item()
            print(f"Success: Fetched ASX_200 ({asx_value:.2f}) from yfinance.")
            return asx_value
        print("Warning: ASX 200 data is empty. Returning fallback.")
        return 7200.0 # Fallback
    except Exception as e:
        print(f"Error fetching ASX 200: {e}. Returning fallback.")
        return 7200.0 # Fallback


# --- INDICATOR CALCULATION FUNCTIONS (Used by fetch_indicator_data) ---

def get_treasury_net_liquidity():
    """
    Calculates Treasury Net Liquidity using FRED data.
    
    Definition:
        Net Liquidity = Fed Balance Sheet (WALCL)
                        - (Treasury General Account (WTREGEN) + Reverse Repo (RRPONTSYD))
    """
    if not fred:
        print("FRED client not initialized. Cannot calculate Net Liquidity.")
        return 100.0

    try:
        # Pull the latest data from FRED
        walcl = float(fred.get_series_latest_release(FRED_WALCL_ID).iloc[-1].item())
        wtregen = float(fred.get_series_latest_release(FRED_WTREGEN_ID).iloc[-1].item())
        rrpontsyd = float(fred.get_series_latest_release(FRED_RRPONTSYD_ID).iloc[-1].item())

        # Correct calculation: WALCL - (TGA + RRP)
        net_liquidity = walcl - (wtregen + rrpontsyd)

        # Detailed output for debugging and validation
        print(f"WALCL (Fed Balance Sheet): {walcl:,.2f}")
        print(f"WTREGEN (TGA): {wtregen:,.2f}")
        print(f"RRPONTSYD (Reverse Repo): {rrpontsyd:,.2f}")
        print(f"Success: Calculated TREASURY_LIQUIDITY = {net_liquidity:,.2f}")

        # Optional sanity check
        if abs(net_liquidity) > abs(walcl) * 2:
            print("⚠️  Warning: Net Liquidity value unusually large — verify FRED data units.")
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
    and EFFR (Effective Federal Funds Rate) as a proxy.
    """
    if not fred:
        print("FRED client not initialized. Cannot calculate SOFR OIS Spread. Returning fallback.")
        return 25.0 # Fallback
    
    try:
        tb3ms = fred.get_series_latest_release(FRED_SOFR_3M_ID).iloc[-1].item()
        effr = fred.get_series_latest_release(FRED_EFFR_ID).iloc[-1].item()
        
        # Calculate the spread in basis points (basis point is 0.01%)
        spread_bps = (float(tb3ms) - float(effr)) * 100 
        
        print(f"Success: Calculated SOFR_OIS_SPREAD ({spread_bps:.2f} bps) from FRED data.")
        return spread_bps
    except Exception as e:
        print(f"FRED API Error for SOFR OIS Spread: {e}. Returning fallback 25.0.")
        return 25.0

def calculate_small_large_ratio():
    """
    Calculates the Small-Cap to Large-Cap ratio (Russell 2000 / S&P 500) using yfinance.
    """
    try:
        # Fetch data for Russell 2000 (^RUT) and S&P 500 (^GSPC)
        tickers = ['^RUT', '^GSPC']
        data = yf.download(tickers, period='1d', interval='1d', progress=False)
        
        if data.empty or len(data.columns) < 2 or data['Close']['^RUT'].isnull().all() or data['Close']['^GSPC'].isnull().all():
            print("Warning: Small/Large Cap ratio data is incomplete. Returning fallback.")
            return 0.42 # Fallback
            
        # Ensure we have the latest closing prices and convert to float
        small_cap = data['Close']['^RUT'].iloc[-1].item()
        large_cap = data['Close']['^GSPC'].iloc[-1].item()
        
        if large_cap == 0:
            print("Warning: Large-cap value is zero. Cannot calculate ratio. Returning fallback.")
            return 0.42
            
        ratio = small_cap / large_cap
        
        print(f"Success: Calculated SMALL_LARGE_RATIO ({ratio:.4f}) from yfinance.")
        return ratio
    except Exception as e:
        print(f"Error calculating Small/Large Cap ratio: {e}. Returning fallback.")
        return 0.42 # Fallback

def fetch_put_call_ratio():
    """
    Fetches the Put/Call Ratio (PCCE Ticker) from Polygon.io, securing the key from the environment.
    """
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


# --- MAIN DATA FETCHER ---

def fetch_indicator_data(indicator_id):
    """
    Fetches the latest data for all indicators, routing to the correct secure function.
    """
    
    FRED_FALLBACK_VALUE = {
        "3Y_YIELD": 3.50, "30Y_YIELD": 4.25, "10Y_YIELD": 4.30, "HY_OAS": 380.0,
        "TREASURY_LIQUIDITY": 100.0,
        "SOFR_OIS": 25.0,
        "BANK_CDS": 85.0,
        "CONSUMER_DELINQUENCIES": 2.2, 
    }

    # --- FRED API CALLS (Single-Point Fetch) ---
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
            
            if fred: 
                try:
                    # 1. FETCH RAW VALUE
                    value = fred.get_series_latest_release(series_id).iloc[-1]
                    
                    # 2. CRITICAL FIX: CONVERT PERCENTAGE TO BASIS POINTS
                    # HY_OAS and CONSUMER_DELINQUENCIES are retrieved as percentage (e.g., 3.15)
                    # and must be converted to basis points (315.0) for scoring.
                    if indicator_id in ["HY_OAS", "CONSUMER_DELINQUENCIES"]:
                        value = float(value) * 100.0
                    
                    # 3. RETURN FINAL FLOAT
                    return float(value)
                    
                except Exception as e:
                    print(f"FRED Error fetching {indicator_id}: {e}. Returning fallback {fallback}.")
                    return fallback
            else:
                print(f"FRED client not initialized. Returning fallback for {indicator_id}.")
                return fallback
        
    # --- CUSTOM FRED API CALLS (Multi-Point Fetch) ---
    elif indicator_id == "SNAP_BENEFITS":
        return _fetch_fred_data_two_points(FRED_SNAP_ID) 
            
    # --- LIVE CALCULATED INDICATORS ---
    elif indicator_id == "TREASURY_LIQUIDITY":
        return get_treasury_net_liquidity()
    elif indicator_id == "SOFR_OIS": 
        return get_sofr_ois_spread()
    elif indicator_id == "MARGIN_DEBT_YOY": 
        return get_finra_margin_debt_yoy()

    # --- YFINANCE / EXTERNAL API CALLS ---
    
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
    elif indicator_id == "PUT_CALL_RATIO": 
        return fetch_put_call_ratio()
    
    # --- UNIMPLEMENTED PLACEHOLDERS ---
    elif indicator_id in ["EARNINGS_REVISION", "GEOPOLITICAL", "FISCAL_RISK"]: 
        return "N/A" 
    
    print(f"Warning: No fetch function defined for indicator ID: {indicator_id}")
    return "N/A"


# --- AI AND ARCHIVE FUNCTIONS ---

def generate_ai_commentary(data_dict, news_context): # Ensure this takes news_context
    """
    Generates the structured AI analysis via the Gemini API, forcing JSON output.
    The narrative combines external news context with internal indicator data, 
    and is structured to be highly actionable.
    """
    import os
    from google import genai 
    from google.genai import types

    # This is a helper function that must be defined somewhere else (or globally)
    # in your script, but is included here for context of what the function needs.
    def prepare_indicator_summary(data_dict):
        summary = []
        # Include all scored indicators
 
        for category, indicators in data_dict.items():
            if isinstance(indicators, list) and category not in ["overall"]:
                summary.append(f"--- {category.upper()} INDICATORS ---")
                for ind in indicators:
                    # Ensure keys exist before formatting
       
                    name = ind.get('name', 'N/A')
                    value = ind.get('value') # Fetch raw value, which might be 'N/A' (str)
                    status = ind.get('status', 'N/A')
                    score = ind.get('score_value', 0.0)
               
                    # *** CRITICAL FIX: Defensive formatting for 'value' ***
                    if isinstance(value, (int, float)):
                        formatted_value = f"{value:.2f}"
                    # Handle two-point data like SNAP (which is a list of two numbers)
                    elif isinstance(value, list) and len(value) == 2:
                        # Displays current and previous value for context (e.g. SNAP)
                        formatted_value = f"{value[1]:.2f} (Prev: {value[0]:.2f})"
                    else:
                        # Fallback for strings like 'N/A', 'Error', or other non-numeric types
                        formatted_value = str(value)
                        
                    # Ensure score is also formatted safely
                    formatted_score = f"{score:.2f}" if isinstance(score, (int, float)) else str(score)

                    summary.append(f"- {name} (Value: {formatted_value}, Status: {status}, Score: {formatted_score})")
        
        # Add key metrics explicitly
        summary.append(f"--- KEY PIVOT METRICS ---")
        summary.append(f"- US 10Y Yield Pivot Threshold: 4.75%")
        summary.append(f"- HY OAS Full-Storm Threshold: 400 bps")

        return "\n".join(summary)
    
    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
    if not GEMINI_API_KEY:
        # Structured fallback for missing key
        return '{"daily_narrative": "AI narrative skipped due to missing API key.", "composite_summary": "Skipped.", "key_actions": ["- Set GEMINI_API_KEY to enable AI analysis."]}'

    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
    except Exception:
        # Structured fallback for client initialization failure
        return '{"daily_narrative": "AI narrative failed to initialize client.", "composite_summary": "Failed.", "key_actions": ["- Check GEMINI_API_KEY format."]}'

    # Define the strict JSON schema
    json_schema = types.Schema(
        type=types.Type.OBJECT,
        properties={
            "daily_narrative": types.Schema(
                type=types.Type.STRING, 
                description="A 1-2 paragraph daily commentary that unifies external news context and internal Atlas indicator analysis."
            ),
            "composite_summary": types.Schema(
                type=types.Type.STRING, 
                description="A single, impactful sentence summarizing the overall risk posture."
            ),
            # Key actions MUST be an array of strings for easy front-end parsing
            "key_actions": types.Schema(
                type=types.Type.ARRAY, 
                items=types.Schema(type=types.Type.STRING), 
                description="A list of 3-5 specific, actionable investment recommendations, focusing on risk-reduction and defense."
            ),
        },
        required=["daily_narrative", "composite_summary", "key_actions"]
    )
    
    # --- Data Preparation for Prompt ---
    indicator_summary = prepare_indicator_summary(data_dict)
    composite_score = data_dict.get("overall", {}).get("score", 0.0)
    composite_status = data_dict.get("overall", {}).get("status", "UNKNOWN")
    
    # --- REVISED SYSTEM INSTRUCTION (ATLAS v3 LOGIC — INDICATORS FIRST + NEWS FEED REFERENCE) ---
    system_instruction = (
        "You are Atlas, a senior macroeconomic analyst. Your task is to generate a concise, "
        "highly actionable institutional investor commentary (target investors and portfolio management: 401K accounts and/or superannuation) "
        "You MUST return the output as a single, valid JSON object adhering strictly to the provided schema. "
        "The analysis for the 'daily_narrative' field must follow the official Atlas commentary structure: "
        
        "1. **Technical Indicator Analysis (Paragraph 1 and 2):** Begin with the internal Atlas data. "
        "Analysis is to be 300-350 words over 2 paragraphs"
        "State the current overall risk posture (e.g., SEVERE RISK) and identify the two-to-three most critical "
        "Red or Amber indicators driving the Composite Score — focusing on Leverage, Liquidity, and Duration risk. "
        "Explain any contradictions (for example, a low VIX despite rising leverage or yields). "
        "Explain what it means for investors and portfolios."
        
        "2. **External Context (Paragraph 3):** Then interpret the global macro and policy tone "
        "External context is to be up to 300 words over one paragraph"
        "using the 'CONTEXTUAL NEWS ARTICLES' provided. "
        "Do NOT embed or reproduce the article titles, URLs, or markdown links directly inside the text. "
        "Instead, reference each source conversationally by outlet and theme (e.g., 'as highlighted by Bloomberg' or 'per Reuters reporting on central bank guidance'). "
        "Direct readers to the 'News Feed below' for the full list of articles reviewed. "
        
        "3. **Trigger Statement (Final Sentence):** Conclude by identifying the key Atlas trigger "
        "that would escalate the posture to FULL-STORM — for instance, a US 10-Year Yield move above 4.75% "
        "or HY OAS widening beyond 400 bps. "
        
        "Maintain a factual, concise institutional tone — analytical, not journalistic. "
        "Never fabricate data or policy commentary, and never restate article titles verbatim."
    )

    # --- REVISED USER PROMPT (INDICATOR-FIRST NARRATIVE, NEWS FEED REFERENCE) ---
    prompt = (
        f"ANALYZE THIS DATA AND CONTEXT:\n\n"
        f"***CRITICAL INSTRUCTION: Begin the 'daily_narrative' with Atlas internal indicator analysis (Paragraph 1 and 2), "
        f"then incorporate global macro context (Paragraph 3), referencing news sources by outlet name only "
        f"and directing readers to the 'News Feed below' for full articles. "
        f"Conclude with the Atlas trigger statement.***\n\n"
        
        f"--- ATLAS INDICATOR SUMMARY ---\n{indicator_summary}\n"
        f"--- OVERALL COMPOSITE SCORE: {composite_score:.2f} (Status: {composite_status}) ---\n\n"
        
        f"--- CONTEXTUAL NEWS ARTICLES ---\n{news_context}\n"
        f"--- END CONTEXT ---\n\n"
        
        f"Generate the final analysis adhering strictly to the JSON schema and the System Instruction’s required narrative structure. "
        f"The 'key_actions' should remain consistent with Atlas defensive guidance: "
        f"focus on deleveraging, defensive sector bias, tactical hedging, credit-spread monitoring, "
        f"and rate-sensitive exposure management."
    )

    
    # Configure the API call to force JSON output
    config = types.GenerateContentConfig(
        system_instruction=system_instruction,
        temperature=0.3, 
        response_mime_type="application/json",
        response_schema=json_schema,
    )

    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=config,
        )
        print("Commentary generated successfully.")
        return response.text
    except Exception as e:
        print(f"Gemini API call failed: {e}")
        # Structured fallback for API failure
        return f'{{"daily_narrative": "Gemini API call failed: {e}", "composite_summary": "Failure", "key_actions": ["- Review API call and data structure."]}}'


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


def _update_indicator_sources(indicators):
    """Adds correct source links to indicators based on their fetch method."""
    YFINANCE_BASE = "https://finance.yahoo.com/quote/"
    FINRA_LINK = "https://www.finra.org/investors/market-and-financial-data/margin-statistics"
    
    YFINANCE_SOURCES = {
        "VIX": YFINANCE_BASE + "%5EVIX/", "GOLD_PRICE": YFINANCE_BASE + "GLD/", 
        "SPX_INDEX": YFINANCE_BASE + "%5EGSPC/", "ASX_200": YFINANCE_BASE + "%5EAXJO/",
        "WTI_CRUDE": YFINANCE_BASE + "USO/", "AUDUSD": YFINANCE_BASE + "AUDUSD=X/",
        "SMALL_LARGE_RATIO": YFINANCE_BASE + "%5ERUT/", "EURUSD": YFINANCE_BASE + "EURUSD=X/"
    }
   
    FRED_SOURCES = {
        "3Y_YIELD": "https://fred.stlouisfed.org/series/DGS3",
        "30Y_YIELD": "https://fred.stlouisfed.org/series/DGS30",
        "10Y_YIELD": "https://fred.stlouisfed.org/series/DGS10",
        "HY_OAS": "https://fred.stlouisfed.org/series/BAMLH0A0HYM2",
        "TREASURY_LIQUIDITY": "https://fred.stlouisfed.org/series/WALCL", 
        "SOFR_OIS": "https://fred.stlouisfed.org/series/SOFR3MAD", 
        "SNAP_BENEFITS": "https://fred.stlouisfed.org/series/SNPTA" 
    }
    
    POLYGON_SOURCES = {
        "PUT_CALL_RATIO": "https://polygon.io/docs/options/get_v2_aggs_ticker__tickervar__prev",
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
        elif indicator_id in CUSTOM_SOURCES:
            indicator["source_link"] = CUSTOM_SOURCES[indicator_id]
        else:
            indicator["source_link"] = indicator.get("source_link", "N/A") 
            
    return indicators


def _compile_escalation_watch(atlas_data):
    """
    Compiles a list of indicators that have breached a pre-defined threshold.
    """
    WATCH_THRESHOLDS = {
        "VIX": {"name": "VIX Index", "threshold": 18.0, "threshold_desc": "Above 18.0"},
        "10Y_YIELD": {"name": "10Y Yield", "threshold": 4.0, "threshold_desc": "Above 4.0%"},
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

        if watch_id in ["EURUSD", "TREASURY_LIQUIDITY"] and isinstance(current_value, (int, float)) and current_value <= watch_info["threshold"]:
            is_breached = True 
        elif watch_id in ["HY_OAS", "SOFR_OIS", "VIX", "10Y_YIELD"] and isinstance(current_value, (int, float)) and current_value >= watch_info["threshold"]:
            is_breached = True 
        
        if is_breached:
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

# --- NEW: PARSING UTILITY FUNCTIONS ---

def parse_ai_response_for_structure(ai_json_string):
    """Parses the JSON response from the AI into a dictionary."""
    if not ai_json_string:
        return {}
    try:
        # Since we force the AI to output JSON in the call, we just load it
        return json.loads(ai_json_string)
    except json.JSONDecodeError as e:
        print(f"FATAL AI Parsing Error: Could not decode AI JSON. {e}")
        return {}

def parse_news_snippets_for_display(raw_news_context):
    """
    Parses the raw news string (formatted as '1. [Title](URL)') into a 
    structured list of objects for the front-end JavaScript display.
    """
    structured_articles = []
    
    # Regex to capture the title and URL from the markdown link format: [Title](URL)
    # Pattern: Digit(s) . [ (Title Group) ] ( (URL Group) )
    pattern = re.compile(r'^\d+\.\s*\[(.*?)\]\((.*?)\)$', re.MULTILINE)
    
    # Find all (Title, URL) tuples
    matches = pattern.findall(raw_news_context)
    
    for title, url in matches:
        # NOTE: The raw news context string does NOT contain the 'snippet' field, 
        # so we use a placeholder as the JavaScript expects it.
        snippet = f"Contextual article. Click title for details."
        
        structured_articles.append({
            'title': title.strip(),
            'url': url.strip(),
            'snippet': snippet
        })

    return structured_articles

# --- NEW: SCORE MAPPING UTILITY ---

def map_score_to_status(score):
    """
    Maps the composite score to the official Atlas risk status based on unified color, emoji, and threshold logic.
    This function must stay synchronized with the frontend getStatusDetails() mapping.
    """

    if score > 12.0:
        # 🔵 FULL-STORM: Extreme Risk
        return "🔵 FULL STORM (EXTREME RISK)"
    elif score > 8.0:
        # 🔴 SEVERE RISK: High Risk
        return "🔴 SEVERE RISK (HIGH RISK)"
    elif score > 4.0:
        # 🟠 ELEVATED RISK: Moderate Risk
        return "🟠 ELEVATED RISK (MODERATE RISK)"
    else:
        # 🟢 MONITOR: Low Risk
        return "🟢 MONITOR (LOW RISK)"


# NOTE: Ensure this is defined before run_update_process calls it!

# --- NEW: SCORE MAPPING COMMENT UTILITY ---

def map_score_to_comment(score):
    """
    Provides a concise, non-AI-generated comment based on the score for backward
    compatibility with dashboard rendering and the archive file.
    """
    # Uses the same thresholds as map_score_to_status
    if score > 12.0:
        return "Extreme systemic stress detected. Full risk-off mode advised."
    elif score > 8.0:
        return "Market stability deteriorating rapidly. High caution required."
    elif score > 4.0:
        return "Risk posture is elevated. Maintain defensive positioning."
    else:
        return "Systemic risk remains contained. Monitor key triggers."

# --- NEW: AI PROMPT DATA PREPARATION UTILITY ---

def prepare_indicator_summary(atlas_data):
    """
    Extracts and formats the five key metrics required for the AI prompt's 
    'Key Indicator Data Snapshot' section.
    """
    # Create a lookup map for easy access (e.g., data_map['VIX_INDEX'])
    data_map = {item['id']: item['value'] for item in atlas_data['macro'] + atlas_data['micro']}

    # Safely extract and format the required key values.
    # We use .get(ID, 0.0) in case any data fetch failed, which prevents a Key Error.
    us10y = data_map.get('US_10Y_YIELD', 0.0)
    vix = data_map.get('VIX_INDEX', 0.0)
    hyoas = data_map.get('HY_OAS', 0.0)
    cpi = data_map.get('CPI_YOY', 0.0)
    pmi = data_map.get('ISM_MANUFACTURING', 0.0)

    # This dictionary's keys MUST match the placeholders in atlas_commentary_prompt.txt:
    # {US10Y_YIELD}, {VIX_VALUE}, {HYOAS_VALUE}, {INFLATION_VALUE}, {PMI_VALUE}
    return {
        "US10Y_YIELD": f"{us10y:.2f}",
        "VIX_VALUE": f"{vix:.2f}",
        "HYOAS_VALUE": f"{hyoas:.0f}", 
        "INFLATION_VALUE": f"{cpi:.1f}", 
        "PMI_VALUE": f"{pmi:.1f}", 
    }

# --- 2. RISK SCORING LOGIC ---

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
        score = 2.0  
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
    source_link = "https://finance.yahoo.com/quote/EURUSD=X"

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
    source_link = "https://finance.yahoo.com/quote/CL=F"

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
    source_link = "https://finance.yahoo.com/quote/AUDUSD=X"

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
    """High Yield Option Adjusted Spread (HY OAS) Scoring - Measures US corporate credit stress."""
    status = "Green"
    note = f"HY OAS at {value:.0f} bps. US credit stress is low and manageable."
    action = "Favour high-quality corporate bonds."
    score = 0.0
    source_link = "https://fred.stlouisfed.org/series/BAMLH0A0HYM2"

    if value >= 500.0:
        status = "Red"
        note = f"HY OAS at {value:.0f} bps. Spreads are aggressively widening. Signals high corporate default risk."
        score = 1.5
        action = "Aggressively exit high-yield exposure and increase corporate quality bias."
    elif value >= 400.0:
        status = "Amber"
        note = f"HY OAS at {value:.0f} bps. Spreads are widening. Caution on lower-rated corporate bonds."
        score = 0.75
        action = "Reduce junk bond exposure; monitor leverage ratios."

    return generate_score_output(status, note, action, score, source_link)


def score_put_call_ratio(value):
    """Put/Call Ratio (PCCE) Scoring - Measures retail options sentiment."""
    status = "Green"
    note = f"PCEE Ratio at {value:.2f}. Balanced options sentiment."
    action = "No change."
    score = 0.0
    source_link = "https://polygon.io/docs/options/get_v2_aggs_ticker__tickervar__prev"

    if value >= 1.0:
        status = "Red"
        note = f"PCEE Ratio at {value:.2f}. Extreme retail options hedging (put-buying). High market fear/bearish sentiment."
        score = 1.0
        action = "Consider contrarian bullish positioning; watch VIX for confirmation."
    elif value <= 0.7:
        status = "Amber"
        note = f"PCEE Ratio at {value:.2f}. Low hedging (call-buying dominance). High complacency/bullish sentiment."
        score = 0.5
        action = "Implement small hedges; avoid chasing market highs."

    return generate_score_output(status, note, action, score, source_link)


def score_spx_index(value):
    """S&P 500 Index Scoring - Measures US broad equity market stress."""
    status = "Green"
    note = f"S&P 500 Index at {value:,.0f}. Strong/stable price action. Low systemic equity risk."
    action = "Maintain equity exposure."
    score = 0.0
    source_link = "https://finance.yahoo.com/quote/%5EGSPC"

    if value <= 4400.0:
        status = "Red"
        note = f"S&P 500 Index at {value:,.0f}. Aggressive sell-off/Correction >12%. Structural equity risk is high."
        action = "Sell/Hedge significant equity exposure. Wait for VIX confirmation below 22."
        score = 1.0
    elif value <= 4800.0: 
        status = "Amber"
        note = f"S&P 500 Index at {value:,.0f}. Moderate pullback from highs. Equity risk is elevated."
        action = "Avoid adding new equity exposure. Maintain existing hedges."
        score = 0.5

    return generate_score_output(status, note, action, score, source_link)

def score_asx_200(value): 
    """S&P/ASX 200 Index Scoring - Measures Australian equity market stress."""
    status = "Green"
    note = f"ASX 200 Index at {value:,.0f}. Stable price action."
    action = "No change."
    score = 0.0
    source_link = "https://finance.yahoo.com/quote/%5EAXJO"

    if value <= 6800.0:
        status = "Red"
        note = f"ASX 200 Index at {value:,.0f}. Significant sell-off. High domestic/regional equity risk."
        action = "Reduce Australian equity exposure."
        score = 1.0
    elif value <= 7200.0:
        status = "Amber"
        note = f"ASX 200 Index at {value:,.0f}. Moderate pullback."
        action = "Watch for further weakness; avoid new exposure."
        score = 0.5

    return generate_score_output(status, note, action, score, source_link)


def score_margin_debt_yoy(value):
    """FINRA Margin Debt YOY Scoring - Measures investor leverage."""
    source_link = "https://www.finra.org/investors/market-and-financial-data/margin-statistics"

    # --- CRITICAL FIX: DEFINE THE CONTEXT STRING ---
    # NOTE: You MUST update the month/year to reflect your actual data cutoff date
    SOURCE_CONTEXT = " (FINRA Data, Oct 2025, Not Seasonally Adjusted)"
    
    if isinstance(value, str):
        if value.upper() == 'N/A':
            return generate_score_output("N/A", "Data N/A: Margin Debt requires FINRA data.", "Cannot score due to missing data.", 0.0, source_link)
        try:
            value = float(value)
        except ValueError:
            return generate_score_output("Error", "Error: Debt value could not be converted to number.", "Cannot score due to data error.", 0.0, "")
    
    status = "Green"
    note = f"Margin Debt YOY at {value:.1f}%{SOURCE_CONTEXT}. Leverage is consolidating/contracting. Lower risk."
    action = "No change."
    score = 0.0

    if value >= 10.0:
        status = "Red"
        note = f"Margin Debt YOY at {value:.1f}%{SOURCE_CONTEXT}. Leverage is expanding aggressively. High risk of forced liquidation if markets fall."
        score = 1.5
        action = "Aggressively deleverage equity exposure; increase cash."
    elif value >= 5.0:
        status = "Amber"
        note = f"Margin Debt YOY at {value:.1f}%{SOURCE_CONTEXT}. Leverage is expanding. Monitor for an acceleration."
        score = 0.5
        action = "Monitor broker-lending rates closely."
    
    return generate_score_output(status, note, action, score, source_link)


def score_small_large_ratio(value):
    """Russell 2000 / S&P 500 Ratio Scoring - Measures market breadth and risk appetite."""
    source_link = "https://finance.yahoo.com/quote/%5ERUT/"

    if isinstance(value, str):
        if value.upper() == 'N/A':
            return generate_score_output("N/A", "Data N/A: Ratio requires YFinance data.", "Cannot score due to missing data.", 0.0, source_link)
        try:
            value = float(value)
        except ValueError:
            return generate_score_output("Error", "Error: Ratio value could not be converted to number.", "Cannot score due to data error.", 0.0, "")

    status = "Red"
    note = f"Ratio at {value:.4f} — small-caps are heavily underperforming. Poor internals."
    action = "Avoid high-risk small-cap exposure."
    score = 1.0 

    if value >= 0.55:
        status = "Green"
        note = f"Ratio at {value:.4f}. Small-caps are outperforming/keeping pace. Strong market breadth."
        action = "Favour high-quality small-cap exposure."
        score = 0.0
    elif value >= 0.45:
        status = "Amber"
        note = f"Ratio at {value:.4f}. Breadth is tentative. Small-caps are consolidating."
        action = "Maintain exposure, but avoid over-concentration in small-caps."
        score = 0.5
        
    return generate_score_output(status, note, action, score, source_link)


def score_treasury_liquidity(value):
    """Treasury Net Liquidity Scoring (Calculated) - Measures systemic liquidity in the US market."""
    status = "Green"
    note = f"Net Liquidity at ${value:.0f}B. Liquidity is robust and supportive of risk assets."
    action = "No change."
    score = 0.0
    source_link = "https://fred.stlouisfed.org/series/WALCL" 

    if value <= 0.0:
        status = "Red"
        note = f"Net Liquidity at ${value:.0f}B. Liquidity is contracting aggressively. High systemic risk."
        score = 2.0 
        action = "Aggressively reduce all risk asset exposure and increase cash/SOFR instruments."
    elif value <= 50.0:
        status = "Amber"
        note = f"Net Liquidity at ${value:.0f}B. Liquidity is tightening. Caution warranted."
        score = 1.0
        action = "Avoid adding new risk assets; monitor Fed repo/balance sheet closely."

    return generate_score_output(status, note, action, score, source_link)


def score_bank_cds(value):
    """Bank CDS (AAA Proxy) Scoring - Measures US banking/counterparty stress."""
    status = "Green"
    note = f"Bank CDS at {value:.0f} bps. Low implied banking stress."
    action = "No change."
    score = 0.0
    source_link = "https://fred.stlouisfed.org/series/AAA" 

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
    status = "Green"
    note = f"Delinquency Rate at {value:.1f}%. Consumer health is stable."
    action = "No change."
    score = 0.0
    source_link = "https://fred.stlouisfed.org/series/DRCCLACBS" 

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

    return generate_score_output(status, note, action, score, source_link)


def score_sofr_ois_spread(value):
    """SOFR/OIS Spread Scoring (Calculated) - Measures dollar funding stress."""
    status = "Green"
    note = f"SOFR/OIS spread is {value:.1f} bps. Dollar funding market is stable."
    action = "No change."
    score = 0.0
    source_link = "https://fred.stlouisfed.org/series/TB3MS" 

    if value >= 50.0:
        status = "Red"
        note = f"SOFR/OIS spread is {value:.1f} bps. Aggressive widening. Signals systemic stress in dollar funding."
        score = 1.5
        action = "Reduce exposure to leveraged institutions; favour USD cash."
    elif value >= 25.0:
        status = "Amber"
        note = f"SOFR/OIS spread is {value:.1f} bps. Spread is widening. Caution on dollar funding markets."
        score = 0.75
        action = "Monitor closely for further widening/dollar liquidity stress."
        
    return generate_score_output(status, note, action, score, source_link)


def score_fiscal_risk(atlas_data):
    """Calculates the FISCAL_RISK score (Max 100) based on four factors."""
    # 1. Social Service Delivery (SNAP Deviation Score) - MAX 25 
    snap_values = next(
        (item['value'] for item in atlas_data['macro'] if item['id'] == 'SNAP_BENEFITS' and isinstance(item['value'], list)), 
        [0.0, 0.0]
    )
    prev_month = snap_values[0]
    curr_month = snap_values[1]
    
    if prev_month > 0:
        snap_mom_change = ((curr_month / prev_month) - 1) * 100
    else:
        snap_mom_change = 0.0

    if snap_mom_change > 10.0 or snap_mom_change < -10.0:
        snap_score = 25
    elif snap_mom_change > 5.0 or snap_mom_change < -5.0:
        snap_score = 15
    else:
        snap_score = 5

    # 2. Public Integrity (Corruption Perception Index - CPI) - MAX 25 
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
    confidence_score = 10 

    fiscal_score = snap_score + corruption_score + civil_unrest_score + confidence_score
    
    return fiscal_score

# --- DATA SCHEMA (Initial State) ---

ATLAS_DATA_SCHEMA = {
    # Indicator data 
    "macro": [
        {"id": "VIX", "name": "VIX index", "value": 0.0, "status": "N/A", "note": "", "action": "No change.", "score_value": 0.0, "source_link": ""},
        {"id": "GOLD_PRICE", "name": "Gold price (GLD)", "value": 0.0, "status": "N/A", "note": "", "action": "No change.", "score_value": 0.0, "source_link": ""},
        {"id": "EURUSD", "name": "EUR/USD exchange rate", "value": 0.0, "status": "N/A", "note": "", "action": "No change.", "score_value": 0.0, "source_link": ""},
        {"id": "WTI_CRUDE", "name": "WTI crude oil ($/bbl)", "value": 0.0, "status": "N/A", "note": "", "action": "No change.", "score_value": 0.0, "source_link": ""},
        {"id": "AUDUSD", "name": "AUD/USD exchange rate", "value": 0.0, "status": "N/A", "note": "", "action": "No change.", "score_value": 0.0, "source_link": ""},
        {"id": "3Y_YIELD", "name": "US 3yr treasury yield", "value": 0.0, "status": "N/A", "note": "", "action": "No change.", "score_value": 0.0, "source_link": ""},
        {"id": "30Y_YIELD", "name": "US 30yr treasury yield", "value": 0.0, "status": "N/A", "note": "", "action": "No change.", "score_value": 0.0, "source_link": ""},
        {"id": "10Y_YIELD", "name": "US 10yr treasury yield", "value": 0.0, "status": "N/A", "note": "", "action": "No change.", "score_value": 0.0, "source_link": ""},
        {"id": "HY_OAS", "name": "High yield OAS (bps)", "value": 0.0, "status": "N/A", "note": "", "action": "No change.", "score_value": 0.0, "source_link": ""},
        {"id": "TREASURY_LIQUIDITY", "name": "Treasury net liquidity", "value": 0.0, "status": "N/A", "note": "Fed Balance - (TGA + ON RRP)", "action": "No change.", "score_value": 0.0, "source_link": ""},
        {"id": "GEOPOLITICAL", "name": "Geopolitical risk", "value": "N/A", "status": "N/A", "note": "", "action": "No change.", "score_value": 0.0, "source_link": ""},
        {"id": "FISCAL_RISK", "name": "Fiscal integrity/debt risk", "value": 0.0, "status": "N/A", "note": "", "action": "No change.", "score_value": 0.0, "source_link": ""},
        {"id": "SNAP_BENEFITS", "name": "SNAP benefits (MoM % change)", "value": [0.0, 0.0], "status": "N/A", "note": "", "action": "No change.", "score_value": 0.0, "source_link": ""},
    ],
    "micro": [
        {"id": "SPX_INDEX", "name": "S&P 500 index", "value": 0.0, "status": "N/A", "note": "", "action": "No change.", "score_value": 0.0, "source_link": ""},
        {"id": "ASX_200", "name": "ASX 200 index", "value": 0.0, "status": "N/A", "note": "", "action": "No change.", "score_value": 0.0, "source_link": ""},
        {"id": "PUT_CALL_RATIO", "name": "Put/Call ratio (PCCE)", "value": 0.0, "status": "N/A", "note": "", "action": "No change.", "score_value": 0.0, "source_link": ""},
        {"id": "MARGIN_DEBT_YOY", "name": "FINRA margin debt (YOY %)", "value": 0.0, "status": "N/A", "note": "", "action": "No change.", "score_value": 0.0, "source_link": ""},
        {"id": "SMALL_LARGE_RATIO", "name": "Small/Large cap ratio", "value": 0.0, "status": "N/A", "note": "", "action": "No change.", "score_value": 0.0, "source_link": ""},
        {"id": "EARNINGS_REVISION", "name": "Earnings revisions ratio", "value": "N/A", "status": "N/A", "note": "", "action": "No change.", "score_value": 0.0, "source_link": ""},
        {"id": "SOFR_OIS", "name": "SOFR OIS Spread (bps)", "value": 0.0, "status": "N/A", "note": "", "action": "No change.", "score_value": 0.0, "source_link": ""},
        {"id": "BANK_CDS", "name": "Bank CDS index (bps)", "value": 0.0, "status": "N/A", "note": "", "action": "No change.", "score_value": 0.0, "source_link": ""},
        {"id": "CONSUMER_DELINQUENCIES", "name": "Consumer delinquencies", "value": 0.0, "status": "N/A", "note": "", "action": "No change.", "score_value": 0.0, "source_link": ""},
    ],
    "overall": {}
}


# --- 4. MAIN PROCESS FUNCTION ---

SCORING_FUNCTIONS = {
    "VIX": score_vix, "3Y_YIELD": score_3y_yield, "10Y_YIELD": score_10y_yield, 
    "30Y_YIELD": score_30y_yield, "GOLD_PRICE": score_gold_price, "EURUSD": score_eurusd, 
    "WTI_CRUDE": score_wti_crude, "AUDUSD": score_audusd, "HY_OAS": score_hy_oas, 
    "SPX_INDEX": score_spx_index, "ASX_200": score_asx_200, "PUT_CALL_RATIO": score_put_call_ratio,
    "MARGIN_DEBT_YOY": score_margin_debt_yoy, "SMALL_LARGE_RATIO": score_small_large_ratio, 
    "TREASURY_LIQUIDITY": score_treasury_liquidity, "BANK_CDS": score_bank_cds, 
    "CONSUMER_DELINQUENCIES": score_consumer_delinquencies, "SOFR_OIS": score_sofr_ois_spread,
}

def run_update_process(atlas_data, news_context=""):
    """
    Runs the full update process, including scoring, overall status calculation, and commentary generation.
    """
    # NOTE: Assuming atlas_data["macro"] and atlas_data["micro"] contain lists of indicator dicts
    # NOTE: Assuming SCORING_FUNCTIONS is defined globally or imported
    all_indicators = atlas_data["macro"] + atlas_data["micro"]
    composite_score = 0.0

    # 1. SCORING LOOP
    for indicator in all_indicators:
        indicator_id = indicator["id"]
        scoring_func = SCORING_FUNCTIONS.get(indicator_id)

        # Skip manual/calculated indicators in this score loop
        if indicator_id in ["FISCAL_RISK", "SNAP_BENEFITS", "GEOPOLITICAL", "EARNINGS_REVISION"]:
            indicator["score_value"] = 0.0
            continue 

        if scoring_func:
            value = indicator.get("value")
            result = scoring_func(value) # Assumes scoring_func returns dict with keys: score_value, status, note, action

            score_value = result["score_value"]
            indicator["status"] = result["status"]
            indicator["note"] = result["note"]
            indicator["action"] = result["action"]
            indicator["score_value"] = score_value
            
            composite_score += score_value
        else:
            indicator["score_value"] = 0.0 
            
    # --- START OF NEW/UPDATED MERGE LOGIC ---

    # 2. PREPARE FOR AI CALL
    # Calculate and store the overall status before calling the AI
    atlas_data["overall"]["score"] = round(composite_score, 2)
    atlas_data["overall"]["status"] = map_score_to_status(composite_score)
    atlas_data["overall"]["comment"] = map_score_to_comment(composite_score)
    # The prepare_indicator_summary call is implicitly handled inside generate_ai_commentary now

    # 3. AI CALL: Generate Commentary & Actions
    # Pass the full indicator data and the raw news context
    ai_output_json_string = generate_ai_commentary(
        data_dict=atlas_data,
        news_context=news_context
    )

    # 4. PARSE AI OUTPUT 
    overall_ai_data = parse_ai_response_for_structure(ai_output_json_string)

    # 5. FINAL ASSEMBLE & UPDATE ATLAS_DATA
    
    # Merge the parsed AI fields into the overall data
    # This adds 'daily_narrative', 'composite_summary', and 'key_actions'
    atlas_data["overall"].update(overall_ai_data) 
    
    # Add the core calculated data (ensures latest values)
    atlas_data["overall"]["date"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # Score and status are already set, but we re-set them here for clarity/finality
    atlas_data["overall"]["score"] = round(composite_score, 2) 
    atlas_data["overall"]["status"] = map_score_to_status(composite_score) 
    
    # Ensure these keys exist even if the AI call failed (uses the fallback from parse_ai_response_for_structure)
    atlas_data["overall"]["daily_narrative"] = atlas_data["overall"].get("daily_narrative", "AI narrative unavailable.")
    atlas_data["overall"]["composite_summary"] = atlas_data["overall"].get("composite_summary", "Summary unavailable.")
    atlas_data["overall"]["key_actions"] = atlas_data["overall"].get("key_actions", ["- No actionable items provided by AI."])

    # 6. PARSE RAW NEWS FOR FRONT-END DISPLAY (Creates the structured list of dicts)
    atlas_data["overall"]["news"] = parse_news_snippets_for_display(news_context)
    
    # Keep the raw news context for debugging
    atlas_data["overall"]["news_context_raw"] = news_context 

    return atlas_data


    # 2. CALCULATE FISCAL RISK (Composite)
    fiscal_indicator = next((item for item in atlas_data['macro'] if item['id'] == 'FISCAL_RISK'), None)
    if fiscal_indicator:
        fiscal_score = score_fiscal_risk(atlas_data)
        fiscal_indicator["value"] = fiscal_score
        fiscal_indicator["status"] = "Amber" if fiscal_score > 50 else "Green"
        fiscal_indicator["note"] = f"Fiscal Score is at {fiscal_score:.0f}. Risk is manageable based on current data."
        fiscal_indicator["action"] = "Monitor VIX and SNAP data closely."

    # 3. Compile OVERALL Score and Status
    score = composite_score
    overall_status_emoji = ""
    overall_status_name = "LOW RISK"
    comment = "LOW RISK. Only minor triggers active. Favour moderate risk-on positioning."
    
    if score >= 6.0:
        overall_status_name = "HIGH RISK"
        comment = "HIGH RISK. Multiple severe triggers active. Aggressively hedge and reduce exposure."
    elif score >= 3.0:
        overall_status_name = "ELEVATED RISK"
        comment = "ELEVATED RISK. Key macro triggers active. Implement cautious hedging and watch credit markets."
    elif score >= 1.0:
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

    # 5. GENERATE THE AI ANALYSIS (News context is not currently used, but the argument is included for future use)
    ai_commentary = generate_ai_commentary(atlas_data)

    # 6. INJECT THE ANALYSIS INTO THE DATA STRUCTURE
    if ai_commentary:
        atlas_data["overall"]["daily_narrative"] = ai_commentary
    else:
        atlas_data["overall"]["daily_narrative"] = f"AI Commentary failed to generate. Current status: {overall_status_name}. Score: {round(score, 2)}."

    # 7. NEWS INTEGRATION (Simple injection for front-end consumption)
    if news_context:
        # Assuming fetch_news_sentiment returns a structured format that can be parsed
        # For simplicity, we'll just inject the raw context, as the parsing function is not available.
        atlas_data["overall"]["news_context_raw"] = news_context 
        
    return atlas_data

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
    for indicator in all_indicators:
        indicator["value"] = fetch_indicator_data(indicator["id"])
    print("Data fetching complete. Starting scoring process.")
    
    # --- FETCH CONTEXTUAL NEWS ---
    print("\n--- Fetching Contextual News Articles ---")
    news_content_for_ai = fetch_news_sentiment(
        query="global economic risk, market outlook, inflation forecast" 
    )
    
    # 4. RUN MAIN PROCESS (Scoring, Narrative, and Saving)
    try:
        updated_atlas_data = run_update_process(
            atlas_data, 
            news_context=news_content_for_ai
        )
        
        # Save the Final Results to the main output file
        with open(OUTPUT_FILE, 'w') as f:
            json.dump(updated_atlas_data, f, indent=4) 
        print(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Success: Atlas JSON successfully generated and written to {OUTPUT_FILE}")

        # Save the narrative/summary to the archive file
        save_to_archive(updated_atlas_data["overall"])
        
    except Exception as e:
        print(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] FATAL ERROR: Atlas update failed. Error: {e}")
        # Log the full traceback if needed (add import traceback and traceback.print_exc())
