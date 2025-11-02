import json
import datetime
import random 
import requests
import yfinance as yf

# --- CONFIGURATION ---

# 1. Output File Path (Must match your front-end fetch)
OUTPUT_FILE = "data/atlas-latest.json" 

# 2. API Keys and Endpoints (Placeholder structure)
# WARNING: Store real keys securely (e.g., environment variables)
API_CONFIG = {
    # 1. LIVE FRED KEY & ENDPOINT
    "FRED_API_KEY": "932518e735c7846a788c5fb8f01f1f89", 
    "FRED_ENDPOINT": "https://api.stlouisfed.org/fred/series/observations",
    
    # 2. EXTERNAL API KEYS & ENDPOINTS
    
    # VIX API (LIVE - Uses AV Key to bypass check, but uses yfinance logic)
    "VIX_API_KEY": "5CGATLAPOEYLJTO7",      
    "VIX_ENDPOINT": "https://www.alphavantage.co/query", 
    
    # GOLD API (LIVE - Uses AV Key to bypass check, but uses yfinance logic)
    "GOLD_API_KEY": "5CGATLAPOEYLJTO7",      
    "GOLD_ENDPOINT": "https://www.alphavantage.co/query", 
    
    # FX API (LIVE - Uses Alpha Vantage for data)
    "FX_API_KEY": "5CGATLAPOEYLJTO7",      
    "FX_ENDPOINT": "https://www.alphavantage.co/query", 
    
    # WTI Crude API (LIVE - Uses Alpha Vantage for data)
    "WTI_API_KEY": "5CGATLAPOEYLJTO7",      
    "WTI_ENDPOINT": "https://www.alphavantage.co/query",
    
    # Equity API (SPX, ASX, Small/Large Ratio, Margin Debt)
    # SPX and ASX are now LIVE (using AV key to bypass placeholder check)
    "EQUITY_API_KEY": "5CGATLAPOEYLJTO7",  
    "EQUITY_ENDPOINT": "https://www.alphavantage.co/query",
    
    # Options/Sentiment API (Still Placeholder for Put/Call Ratio)
    "PUT_CALL_API_KEY": "qYLFTWtQSFs3NntmnCeQDy8d5asiA6_3",      # <-- YOUR LIVE KEY
    "PUT_CALL_ENDPOINT": "https://api.polygon.io/v2/aggs/ticker/PCCE/prev", # Polygon endpoint for CBOE Total Put/Call Ratio (PCCE)
    
    # Credit/CDS API (Still Placeholder)
    "CREDIT_API_KEY": "YOUR_CREDIT_KEY_HERE",
    "CREDIT_ENDPOINT": "YOUR_CREDIT_API_ENDPOINT",

    # Interest Rate Spread API (Still Placeholder)
    "SOFR_API_KEY": "YOUR_SOFR_KEY_HERE",
    "SOFR_ENDPOINT": "YOUR_SOFR_API_ENDPOINT", 
    
    # Dedicated Macro API (Still Placeholder)
    "MACRO_API_KEY": "YOUR_MACRO_KEY_HERE",
    "MACRO_ENDPOINT": "YOUR_MACRO_API_ENDPOINT", 
    
    # Earnings/Analyst API (Still Placeholder)
    "EARNINGS_API_KEY": "YOUR_EARNINGS_KEY_HERE",
    "EARNINGS_ENDPOINT": "YOUR_EARNINGS_API_ENDPOINT", 
    
    # 3. FRED SERIES IDS (The four successful series)
    "FRED_3YR_ID": "DGS3",
    "FRED_30YR_ID": "DGS30",
    "FRED_10YR_ID": "DGS10",  
    "FRED_HYOAS_ID": "BAMLH0A0HYM2", 
}

# --- 1. DATA FETCHING AND PARSING FUNCTIONS (UPDATED FOR FALLBACK) ---

def fetch_indicator_data(indicator_id):
    """
    Fetches the latest data for FRED indicators or returns a random value for others.
    """
    
    # Define a safe fallback value for FRED series (e.g., median of their risk band)
    FRED_FALLBACK_VALUE = {
        "3Y_YIELD": 3.50,
        "30Y_YIELD": 4.25,
        "10Y_YIELD": 4.30,
        "HY_OAS": 380.0,
    }

    # --- FRED API CALLS (For Yields and other FRED series) ---
    fred_series_map = {
        "3Y_YIELD": API_CONFIG["FRED_3YR_ID"],
        "30Y_YIELD": API_CONFIG["FRED_30YR_ID"],
        "10Y_YIELD": API_CONFIG["FRED_10YR_ID"],
        "HY_OAS": API_CONFIG["FRED_HYOAS_ID"],
    }

    if indicator_id in fred_series_map:
        series_id = fred_series_map[indicator_id]
        
        # Determine the fallback value for this specific indicator
        fallback = FRED_FALLBACK_VALUE.get(indicator_id, 0.0)
        
        try:
            params = {
                "series_id": series_id,
                "api_key": API_CONFIG["FRED_API_KEY"],
                "file_type": "json",
                "observation_start": (datetime.date.today() - datetime.timedelta(days=30)).strftime("%Y-%m-%d"),
                "sort_order": "desc",
                "limit": 1
            }
            response = requests.get(API_CONFIG["FRED_ENDPOINT"], params=params)
            response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
            data = response.json()
            
            # Find the latest non-dot value
            for obs in data.get("observations", []):
                if obs["value"] != ".":
                    return float(obs["value"]) 
            
            print(f"FRED Warning: No valid data found for {indicator_id} ({series_id}). Returning fallback value {fallback}.")
            return fallback

        except requests.exceptions.RequestException as e:
            # Return a fallback number instead of None on failure
            print(f"FRED Error fetching {indicator_id} ({series_id}): {e}. Returning fallback value {fallback}.")
            return fallback
            
    # --- PLACEHOLDER API CALLS (For all other indicators) ---
    
# --- PLACEHOLDER API CALLS (For all other indicators) ---
    
    # Macro Indicators (Remaining Placeholders)
    elif indicator_id == "VIX": 
        return fetch_external_data("VIX_ENDPOINT", "VIX_API_KEY", "VIX", 22.0)
    elif indicator_id == "GOLD_PRICE": 
        return fetch_external_data("GOLD_ENDPOINT", "GOLD_API_KEY", "GOLD_PRICE", 2000.00) 
    elif indicator_id == "EURUSD": 
        return fetch_external_data("FX_ENDPOINT", "FX_API_KEY", "EURUSD", 1.14) 
    elif indicator_id == "WTI_CRUDE": 
        return fetch_external_data("WTI_ENDPOINT", "WTI_API_KEY", "WTI_CRUDE", 80.0) 
    elif indicator_id == "AUDUSD": 
        return fetch_external_data("FX_ENDPOINT", "FX_API_KEY", "AUDUSD", 0.68) 
    elif indicator_id == "TREASURY_LIQUIDITY": 
        # Using a new dedicated API for a unique macro data source
        return fetch_external_data("MACRO_ENDPOINT", "MACRO_API_KEY", "TREASURY_LIQUIDITY", 100.0) 

    # Micro Indicators (Remaining Placeholders)
    elif indicator_id == "SPX_INDEX": 
        return fetch_external_data("EQUITY_ENDPOINT", "EQUITY_API_KEY", "SPX_INDEX", 4400.0) 
    elif indicator_id == "ASX_200": 
        return fetch_external_data("EQUITY_ENDPOINT", "EQUITY_API_KEY", "ASX_200", 8600.0)
    elif indicator_id == "SOFR_OIS": 
        # Using a new dedicated API for interest rate spreads
        return fetch_external_data("SOFR_ENDPOINT", "SOFR_API_KEY", "SOFR_OIS", 25.0) 
    elif indicator_id == "PUT_CALL_RATIO": 
        return fetch_external_data("PUT_CALL_ENDPOINT", "PUT_CALL_API_KEY", "PUT_CALL_RATIO", 0.9)
    elif indicator_id == "SMALL_LARGE_RATIO": 
        # Using the same API as Equity Indices for simple ratio data
        return fetch_external_data("EQUITY_ENDPOINT", "EQUITY_API_KEY", "SMALL_LARGE_RATIO", 0.42)
    elif indicator_id == "EARNINGS_REVISION": 
        # Using a new dedicated API for analyst data
        return fetch_external_data("EARNINGS_ENDPOINT", "EARNINGS_API_KEY", "EARNINGS_REVISION", -2.0) 
    elif indicator_id == "MARGIN_DEBT_YOY": 
        # Using the same API as Equity Indices for broker data
        return fetch_external_data("EQUITY_ENDPOINT", "EQUITY_API_KEY", "MARGIN_DEBT_YOY", 20.0) 
    elif indicator_id == "BANK_CDS": 
        # Using a new dedicated API for credit default swaps
        return fetch_external_data("CREDIT_ENDPOINT", "CREDIT_API_KEY", "BANK_CDS", 80.0) 
    elif indicator_id == "CONSUMER_DELINQUENCIES": 
        # Using the same API as Credit Default Swaps for broader credit data
        return fetch_external_data("CREDIT_ENDPOINT", "CREDIT_API_KEY", "CONSUMER_DELINQUENCIES", 3.0) 
    
    return None # Should not be reached

# Insert this new function near the top of your script

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
         # Check for a different error format (e.g., if the symbol is bad)
         if not data and "Note" in data:
             raise ValueError(f"API note/error: {data.get('Note')}")
         
         raise ValueError("Global Quote data is empty or missing.")

    # Price is in the "05. price" field
    return float(global_quote.get("05. price"))

def _fetch_yfinance_quote(symbol):
    """Internal function to fetch the latest close price using yfinance."""
    ticker = yf.Ticker(symbol) 
    
    # Fetch the latest available daily data
    data = ticker.history(period="1d", interval="1d") 

    if data.empty:
        raise ValueError(f"yfinance returned no data for symbol {symbol}.")

    # The current price is the latest available 'Close' price
    close_price = data['Close'].iloc[-1]
    
    # Ensure it is a standard float
    return float(close_price)

def _fetch_polygon_data(endpoint, api_key):
    """Internal function to fetch Put/Call Ratio data from the Polygon.io 'prev' endpoint."""
    
    # The 'prev' endpoint gets the last aggregate bar for the ticker (PCCE)
    # The API key must be passed as a query parameter
    params = {
        "apiKey": api_key 
    }
    
    response = requests.get(endpoint, params=params)
    response.raise_for_status() 
    data = response.json()
    
    # Polygon 'prev' endpoint returns results in an array
    results = data.get("results")
    if not results or not isinstance(results, list) or len(results) == 0:
         raise ValueError("Polygon API results array is empty or missing.")

    # PCCE ticker price is usually found in the 'c' (close) field of the first result object
    # The CBOE Total Put/Call Ratio is typically treated as a price for these data feeds.
    pcr_value = results[0].get("c") 

    if pcr_value is None:
         raise ValueError("Polygon API data parsing failed: 'c' (close) price is missing in the result.")
         
    return float(pcr_value)

def fetch_external_data(endpoint_key, api_key_key, indicator_id, fallback_value):
    """
    Generic function to fetch data from external APIs.
    Routes traffic to yfinance, Polygon, or Alpha Vantage, and returns "N/A" for unautomated indicators.
    """
    endpoint = API_CONFIG.get(endpoint_key)
    api_key = API_CONFIG.get(api_key_key)

    # 1. PLACEHOLDER CHECK (Universal check for any indicator using placeholder keys)
    if endpoint.startswith("YOUR_") or api_key.startswith("YOUR_"):
        print(f"Placeholder: API endpoint or key for {indicator_id} is not configured. Returning fallback value {fallback_value}.")
        # NOTE: For the remaining four indicators that hit this check, we must ensure
        # their API_CONFIG keys are NOT "YOUR_..." so they fall to the N/A block (Section 5).
        return fallback_value
    
    # --- YFINANCE LOGIC (VIX, Gold, SPX, ASX, SMALL_LARGE_RATIO, WTI_CRUDE, AUDUSD) ---
    
    # 2. YFINANCE LOGIC 
    # Consolidated all reliable single-quote fetches here, including the previously failing WTI and AUDUSD.
    if indicator_id in ["VIX", "GOLD_PRICE", "SPX_INDEX", "ASX_200", 
                        "SMALL_LARGE_RATIO", "WTI_CRUDE", "AUDUSD"]:
        try:
            # --- Single Ticker Fetch ---
            if indicator_id not in ["SMALL_LARGE_RATIO"]:
                symbol_map = {
                    "VIX": "^VIX",
                    "GOLD_PRICE": "GC=F",
                    "SPX_INDEX": "^GSPC",
                    "ASX_200": "^AXJO",
                    "WTI_CRUDE": "CL=F",       # Moved from Alpha Vantage
                    "AUDUSD": "AUDUSD=X"       # Moved from Alpha Vantage
                }
                symbol = symbol_map[indicator_id]
                value = _fetch_yfinance_quote(symbol)
                
                # Use .4f for FX pairs, .2f for everything else in this block
                formatting = "{:.4f}" if indicator_id in ["AUDUSD"] else "{:.2f}"
                print(f"Success: Fetched {indicator_id} ({formatting.format(value)}) from yfinance.")
                return value 
                
            # --- Ratio Calculation (SMALL_LARGE_RATIO) ---
            elif indicator_id == "SMALL_LARGE_RATIO":
                small_cap_symbol = "^RUT" # Russell 2000 Index
                large_cap_symbol = "^GSPC" # S&P 500 Index
                
                small_cap_value = _fetch_yfinance_quote(small_cap_symbol)
                large_cap_value = _fetch_yfinance_quote(large_cap_symbol)
                
                ratio = small_cap_value / large_cap_value
                
                print(f"Success: Calculated {indicator_id} ({ratio:.4f}) from yfinance data.")
                return ratio 

        except Exception as e:
            print(f"{indicator_id} yfinance Error: Failed to fetch data: {e}. Returning fallback value {fallback_value}.")
            return fallback_value
            
    # --- POLYGON LOGIC (PUT_CALL_RATIO) ---
    
    # 3. POLYGON LOGIC (PUT_CALL_RATIO)
    if indicator_id == "PUT_CALL_RATIO":
        try:
            pcr_value = _fetch_polygon_data(endpoint, api_key)
            
            print(f"Success: Fetched {indicator_id} ({pcr_value:.2f}) from Polygon.io.")
            return pcr_value
            
        except Exception as e:
            print(f"{indicator_id} API Error: Data fetch failed: {e}. Returning fallback value {fallback_value}.")
            return fallback_value
            
    # --- ALPHA VANTAGE LOGIC (ONLY EURUSD REMAINS) ---
            
    # 4. ALPHA VANTAGE FX & COMMODITY LOGIC 
    if indicator_id in ["EURUSD"]: # <-- ONLY EURUSD REMAINS
        try:
            symbol_map = {"EURUSD": "EURUSD"} 
            symbol = symbol_map[indicator_id]
            
            av_value = _fetch_alpha_vantage_quote(symbol, 
                                                  api_key, 
                                                  endpoint)
            
            formatting = "{:.4f}"
            print(f"Success: Fetched {indicator_id} ({formatting.format(av_value)}) from Alpha Vantage.")
            return av_value 
            
        except Exception as e:
            print(f"{indicator_id} API Error: Data fetch failed: {e}. Returning fallback value {fallback_value}.")
            return fallback_value
            
    # 5. FINAL MANUAL/N/A LOGIC 
    # This block handles indicators that are not yet automated by a live API.
    else:
        unautomated_indicators = [
            "TREASURY_LIQUIDITY", "SOFR_OIS", "EARNINGS_REVISION", 
            "MARGIN_DEBT_YOY", "BANK_CDS", "CONSUMER_DELINQUENCIES"
        ]
        
        if indicator_id in unautomated_indicators:
            na_value = "N/A"
            print(f"Data N/A Success: {indicator_id} is currently set to '{na_value}'. Requires external API.")
            return na_value
            
        else: 
            # This is the final catch-all if an unexpected indicator is processed.
            print(f"Generic Success: {indicator_id} is correctly routed. Logic not implemented. Returning fallback value {fallback_value}.")
            return fallback_value  

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
        note = f"~{value:.2f} band. Elevated and episodic. Recent intraday spikes to ~22–23."
        action = "VIX ≥ 22 → partial de-risk; sustained >24–25 → escalate hedges / go to max Storm."
        score = 1.0 
    elif value >= 18.0:
        status = "Amber"
        note = f"~{value:.2f} band. Volatility is elevated but contained."
        action = "Monitor closely for breaks above 22."
        score = 0.5

    return {"name": "VIX (US implied vol)", "status": status, "note": note, "source_link": source_link, "action": action, "score_value": score}

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
        note = f"~{value:.2f}% (latest daily Treasury series / market quotes). Medium-term rate pressure."
        action = "Avoid intermediate locks; prefer short/floating rate instruments."
        score = 0.5
        
    return {"name": "US 3-yr Treasury yield", "status": status, "note": note, "source_link": source_link, "action": action, "score_value": score}

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
        note = f"~{value:.2f}% (latest market quotes / curve prints). Elevated yields."
        action = "Watch the Atlas pivot at 4.75%; favour short duration."
        score = 0.5
        
    return {"name": "US 10-yr Treasury yield", "status": status, "note": note, "source_link": source_link, "action": action, "score_value": score}

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
        note = f"~{value:.2f}% (latest market quotes). Elevated long-term yields reflecting fiscal risk/inflation concerns."
        action = "Watch the 5.0% threshold. Limit long duration locks."
        score = 0.5
        
    return {"name": "US 30-yr Treasury yield", "status": status, "note": note, "source_link": source_link, "action": action, "score_value": score}

def score_gold(value):
    """Gold (USD/oz) Scoring - High prices signal risk-off/safe-haven regime."""
    
    status = "Green"
    note = f"Gold price at ${value:,.2f} USD/oz. Stable pricing."
    action = "No change."
    score = 0.0
    source_link = "https://www.reuters.com/markets/commodities/gold/"

    if value >= 2100.00:
        status = "Red"
        note = f"Gold remains bid—current price at ${value:,.2f} USD/oz. Institutional safe-haven signal."
        action = "Consider/maintain moderate gold hedges (5–10%)."
        score = 1.0 

    elif value >= 2000.00:
        status = "Amber"
        note = f"Gold price at ${value:,.2f} USD/oz. Elevated status due to persistent geopolitical/fiscal risk."
        action = "Monitor price action and central bank activity."
        score = 0.5
        
    return {"name": "Gold (USD/oz)", "status": status, "note": note, "source_link": source_link, "action": action, "score_value": score}

def score_eurusd(value):
    """EURUSD Scoring - Measures global liquidity and US Dollar strength."""
    
    status = "Green"
    note = f"EURUSD at {value:.4f}. Normal FX conditions; US Dollar is stable."
    action = "No change."
    score = 0.0
    source_link = "https://www.tradingview.com/symbols/EURUSD/" 

    # Threshold for Red: Strong US Dollar, risk-off signal (approaching parity or below)
    if value <= 1.05:
        status = "Red"
        note = f"EURUSD at {value:.4f}. US Dollar aggressively strong. Significant risk-off or liquidity squeeze signal."
        action = "Increase US Dollar cash weighting; monitor emerging market FX."
        score = 1.0 

    # Threshold for Amber: Dollar strength is evident, risk is building (Example: 1.05 to 1.10)
    elif value <= 1.10: 
        status = "Amber"
        note = f"EURUSD at {value:.4f}. US Dollar strength is evident; global liquidity is tightening."
        action = "Monitor for acceleration towards parity (1.00)."
        score = 0.5
        
    return {"name": "EURUSD", "status": status, "note": note, "source_link": source_link, "action": action, "score_value": score}

def score_wti_crude(value):
    """WTI Crude Oil Scoring - Measures global inflation and geopolitical risk."""
    
    status = "Green"
    note = f"WTI Crude at ${value:.2f}/bbl. Normal price range, favorable for growth."
    action = "No change."
    score = 0.0
    source_link = "https://www.eia.gov/dnav/pet/hist/rwtc.htm" 

    # Threshold for Red: Price indicates strong inflationary/geopolitical risk
    if value >= 90.0:
        status = "Red"
        note = f"WTI Crude at ${value:.2f}/bbl. Aggressively high price. Major inflation headwind and geopolitical risk signal."
        action = "Increase defensive exposure. Monitor supply lines closely."
        score = 1.0 

    # Threshold for Amber: Price is elevated, creating modest pressure
    elif value >= 75.0: 
        status = "Amber"
        note = f"WTI Crude at ${value:.2f}/bbl. Elevated price range, watch for breaks above $90/bbl."
        action = "Ensure portfolio is hedged against inflation risks."
        score = 0.5
        
    return {"name": "WTI Crude Oil", "status": status, "note": note, "source_link": source_link, "action": action, "score_value": score}

def score_audusd(value):
    """AUDUSD Scoring - Measures global risk appetite and US Dollar strength."""
    
    status = "Green"
    note = f"AUDUSD at {value:.4f}. Favorable FX conditions; AUD reflects risk-on sentiment."
    action = "No change."
    score = 0.0
    source_link = "https://www.tradingview.com/symbols/AUDUSD/" 

    # Threshold for Red: AUD weak, indicating strong risk-off/USD dominance
    if value <= 0.6500:
        status = "Red"
        note = f"AUDUSD at {value:.4f}. AUD remains under pressure. Strong risk-off or persistent US Dollar strength."
        action = "Favour US Dollar liquidity over AUD assets; watch commodity prices."
        score = 1.0 

    # Threshold for Amber: AUD under modest pressure
    elif value <= 0.7000: 
        status = "Amber"
        note = f"AUDUSD at {value:.4f}. AUD is consolidating. Global risk appetite is tentative."
        action = "Monitor closely for breaks below 0.6500."
        score = 0.5
        
    return {"name": "AUDUSD", "status": status, "note": note, "source_link": source_link, "action": action, "score_value": score}

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
        
    return {"name": "Credit Spreads (HY OAS)", "status": status, "note": note, "source_link": source_link, "action": action, "score_value": score}

def score_spx(value):
    """S&P 500 Scoring - Measures US Equity Risk and General Market Sentiment (Micro Indicator)."""
    
    status = "Green"
    note = f"S&P 500 Index at {value:,.0f}. Trading near highs, risk-on sentiment prevailing."
    action = "No change."
    score = 0.0
    source_link = "https://finance.yahoo.com/quote/%5EGSPC" 

    # Threshold for Red: Significant correction/bear market territory
    if value <= 4200.0:
        status = "Red"
        note = f"S&P 500 Index at {value:,.0f}. Aggressive sell-off/Correction >12%. Structural equity risk is high."
        action = "Sell/Hedge significant equity exposure. Wait for VIX confirmation below 22."
        score = 1.0 

    # Threshold for Amber: Minor correction/pullback
    elif value <= 4500.0: 
        status = "Amber"
        note = f"S&P 500 Index at {value:,.0f}. Moderate pullback from highs. Equity risk is elevated."
        action = "Avoid adding new equity exposure. Maintain existing hedges."
        score = 0.5
        
    return {"name": "S&P 500 Index", "status": status, "note": note, "source_link": source_link, "action": action, "score_value": score}

def score_asx200(value):
    """S&P/ASX 200 Scoring - Measures Australian Equity Risk and Domestic Sentiment (Micro Indicator)."""
    
    status = "Green"
    note = f"ASX 200 Index at {value:,.0f}. Trading near highs, bullish sentiment prevailing."
    action = "No change."
    score = 0.0
    source_link = "https://finance.yahoo.com/quote/%5EAXJO" 

    # Threshold for Red: Significant correction/bear market territory
    if value <= 8300.0:
        status = "Red"
        note = f"ASX 200 Index at {value:,.0f}. Significant sell-off / Correction >10%. Structural equity risk is high, particularly in Financials/Materials."
        action = "Sell/Hedge significant AU equity exposure. Wait for VIX/HY OAS confirmation."
        score = 1.0 

    # Threshold for Amber: Minor correction/pullback
    elif value <= 8700.0: 
        status = "Amber"
        note = f"ASX 200 Index at {value:,.0f}. Moderate pullback from highs. Australian equity risk is elevated."
        action = "Avoid adding new AU equity exposure. Monitor commodity prices (Iron Ore/Copper)."
        score = 0.5
        
    return {"name": "S&P/ASX 200 Index", "status": status, "note": note, "source_link": source_link, "action": action, "score_value": score}

def score_sofr_ois(value):
    """SOFR-OIS Spread Scoring - Measures US funding stress (Micro Indicator)."""
    
    # CRITICAL FIX: Handle "N/A" and other string inputs to prevent KeyError
    if isinstance(value, str):
        return {
            "name": "SOFR–OIS Spread", 
            "status": "N/A", 
            "note": "Data N/A: SOFR-OIS Spread requires external API.", 
            "source_link": "https://fred.stlouisfed.org/series/OISSOFR", 
            "action": "Cannot score due to missing data.", 
            "score_value": 0.0, # Neutral score to allow sorting
            "grade": 0 # Assuming 'grade' is used elsewhere, set to neutral
        }

    # Convert to float for comparison if it was a numeric string before this check
    try:
        value = float(value)
    except ValueError:
        # Fallback if the string wasn't "N/A" but still failed conversion
        return {
            "name": "SOFR–OIS Spread", 
            "status": "Error", 
            "note": "Error: SOFR-OIS value could not be converted to number.", 
            "source_link": "Error", 
            "action": "Cannot score due to data error.", 
            "score_value": 0.0,
            "grade": 0
        }

    # --- Scoring Logic for numeric values ---
    status = "Green"
    note = f"SOFR-OIS spread at {value:.1f} bps. Funding markets are calm; spread within normal range."
    action = "No change."
    score = 0.0
    source_link = "https://fred.stlouisfed.org/series/OISSOFR" 

    if value >= 40.0:
        status = "Red"
        note = f"SOFR-OIS spread at {value:.1f} bps. Elevated funding market stress. Indicates acute counterparty risk / liquidity fear."
        action = "Increase cash weighting and monitor closely for structural funding issues. Avoid adding credit risk."
        score = 1.0 

    elif value >= 25.0: 
        status = "Amber"
        note = f"SOFR-OIS spread at {value:.1f} bps. Spread widening; caution warranted in short-term funding markets."
        action = "Monitor for acceleration above 40 bps. Check SOFR/Treasury basis."
        score = 0.5
        
    return {
        "name": "SOFR–OIS Spread", 
        "status": status, 
        "note": note, 
        "source_link": source_link, 
        "action": action, 
        "score_value": score
        # Note: Add 'grade' and 'color' if they are used by your dashboard
    }
def score_sofr_ois(value):
    """SOFR-OIS Spread Scoring - Measures US funding stress (Micro Indicator)."""
    
    # CRITICAL FIX: Handle "N/A" and other string inputs to prevent KeyError
    if isinstance(value, str):
        return {
            "name": "SOFR–OIS Spread", 
            "status": "N/A", 
            "note": "Data N/A: SOFR-OIS Spread requires external API.", 
            "source_link": "https://fred.stlouisfed.org/series/OISSOFR", 
            "action": "Cannot score due to missing data.", 
            "score_value": 0.0, # Neutral score to allow sorting
            "grade": 0 # Assuming 'grade' is used elsewhere, set to neutral
        }

    # Convert to float for comparison if it was a numeric string before this check
    try:
        value = float(value)
    except ValueError:
        # Fallback if the string wasn't "N/A" but still failed conversion
        return {
            "name": "SOFR–OIS Spread", 
            "status": "Error", 
            "note": "Error: SOFR-OIS value could not be converted to number.", 
            "source_link": "Error", 
            "action": "Cannot score due to data error.", 
            "score_value": 0.0,
            "grade": 0
        }

    # --- Scoring Logic for numeric values ---
    status = "Green"
    note = f"SOFR-OIS spread at {value:.1f} bps. Funding markets are calm; spread within normal range."
    action = "No change."
    score = 0.0
    source_link = "https://fred.stlouisfed.org/series/OISSOFR" 

    if value >= 40.0:
        status = "Red"
        note = f"SOFR-OIS spread at {value:.1f} bps. Elevated funding market stress. Indicates acute counterparty risk / liquidity fear."
        action = "Increase cash weighting and monitor closely for structural funding issues. Avoid adding credit risk."
        score = 1.0 

    elif value >= 25.0: 
        status = "Amber"
        note = f"SOFR-OIS spread at {value:.1f} bps. Spread widening; caution warranted in short-term funding markets."
        action = "Monitor for acceleration above 40 bps. Check SOFR/Treasury basis."
        score = 0.5
        
    return {
        "name": "SOFR–OIS Spread", 
        "status": status, 
        "note": note, 
        "source_link": source_link, 
        "action": action, 
        "score_value": score
        # Note: Add 'grade' and 'color' if they are used by your dashboard
    }

def score_treasury_liquidity(value):
    """NEW: US Treasury liquidity (Dealer/ADTV) Scoring (Macro Indicator)."""
    
    # CRITICAL FIX: Handle "N/A" and other string inputs to prevent KeyError
    if isinstance(value, str):
        return {
            "name": "US Treasury liquidity (Dealer/ADTV)", 
            "status": "N/A", 
            "note": "Data N/A: Treasury liquidity data requires external API.", 
            "source_link": "U.S. Department of the Treasury (placeholder)", 
            "action": "Cannot score due to missing data.", 
            "score_value": 0.0, # Neutral score to allow sorting
            "grade": 0 # Assuming 'grade' is used elsewhere, set to neutral
        }

    # Convert to float for comparison if it was a numeric string before this check
    try:
        value = float(value)
    except ValueError:
        # Fallback if the string wasn't "N/A" but still failed conversion
        return {
            "name": "US Treasury liquidity (Dealer/ADTV)", 
            "status": "Error", 
            "note": "Error: Treasury liquidity value could not be converted to number.", 
            "source_link": "Error", 
            "action": "Cannot score due to data error.", 
            "score_value": 0.0,
            "grade": 0
        }

    # --- Scoring Logic for numeric values ---
    status = "Green"
    note = f"Dealer ADTV at ${value:.1f}B. Market functioning, no broad dealer freeze flagged."
    action = "Liquidity ok — price risk dominates."
    score = 0.0
    source_link = "U.S. Department of the Treasury (placeholder)"

    # Placeholder Logic: Assume lower ADTV = lower liquidity/stress
    if value <= 80.0:
        status = "Red"
        note = f"Dealer ADTV at ${value:.1f}B. Liquidity strain is evident; dealer capacity flagged."
        action = "Increase cash weighting and avoid complex fixed income trades."
        score = 1.0 
    elif value <= 95.0:
        status = "Amber"
        note = f"Dealer ADTV at ${value:.1f}B. Liquidity is tightening; monitor trade volumes closely."
        action = "Monitor closely for breaks below $80B."
        score = 0.5
        
    return {
        "name": "US Treasury liquidity (Dealer/ADTV)", 
        "status": status, 
        "note": note, 
        "source_link": source_link, 
        "action": action, 
        "score_value": score
        # Note: Add 'grade' and 'color' if they are used by your dashboard
    }

def score_put_call_ratio(value):
    """NEW: Put/Call ratio (CBOE) Scoring (Micro Indicator)."""
    status = "Amber"
    note = f"P/C ratio at ~{value:.2f} (hedging bias)."
    action = ">1.2 → panic; <0.7 → complacency."
    score = 0.5
    source_link = "https://www.cboe.com/us/options/market_statistics/daily/"

    if value >= 1.2:
        status = "Red"
        note = f"P/C ratio at ~{value:.2f}. Extreme hedging and fear (Panic)."
        action = "Tactically use extreme fear as a potential (short-term) contrarian entry signal."
        score = 1.0 
    elif value <= 0.7:
        status = "Green"
        note = f"P/C ratio at ~{value:.2f}. Extreme complacency; low hedging activity."
        action = "Extreme complacency is a long-term risk signal; maintain protective hedges."
        score = 0.0 # Low score is intentional as it signals structural risk, not immediate panic
    # 0.7 < value < 1.2 is Amber (Normal or hedging bias)
        
    return {"name": "Put/Call ratio (CBOE)", "status": status, "note": note, "source_link": source_link, "action": action, "score_value": score}

def score_small_large_ratio(value):
    """NEW: Small-cap / Large-cap ratio Scoring (Micro Indicator)."""
    status = "Red"
    note = f"Ratio at ~{value:.2f} — small-caps underperforming."
    action = "<0.40 → strong red; internals fragile."
    score = 1.0
    source_link = "Reference Russell 2000 / S&P 500 (placeholder)"

    if value >= 0.45:
        status = "Green"
        note = f"Ratio at ~{value:.2f}. Small-caps performing well; strong market internals."
        action = "No change."
        score = 0.0 
    elif value >= 0.40:
        status = "Amber"
        note = f"Ratio at ~{value:.2f}. Small-caps under pressure; monitor market breadth."
        action = "Monitor closely for breaks below 0.40."
        score = 0.5
    # value < 0.40 is Red

    return {"name": "Small-cap / Large-cap ratio", "status": status, "note": note, "source_link": source_link, "action": action, "score_value": score}

def score_earnings_revision(value):
    """NEW: Earnings-revision breadth Scoring (Micro Indicator)."""
    
    # CRITICAL FIX: Handle "N/A" and other string inputs to prevent KeyError
    if isinstance(value, str):
        return {
            "name": "Earnings-revision breadth", 
            "status": "N/A", 
            "note": "Data N/A: Earnings revision data requires external API.", 
            "source_link": "FactSet / Bloomberg consensus data (placeholder)", 
            "action": "Cannot score due to missing data.", 
            "score_value": 0.0, # Neutral score to allow sorting
            "grade": 0 # Assuming 'grade' is used elsewhere, set to neutral
        }

    # Convert to float for comparison if it was a numeric string before this check
    try:
        value = float(value)
    except ValueError:
        # Fallback if the string wasn't "N/A" but still failed conversion
        return {
            "name": "Earnings-revision breadth", 
            "status": "Error", 
            "note": "Error: Earnings revision value could not be converted to number.", 
            "source_link": "Error", 
            "action": "Cannot score due to data error.", 
            "score_value": 0.0,
            "grade": 0
        }

    # --- Scoring Logic for numeric values ---
    status = "Amber"
    note = f"~{value:.0f}% net revisions. Earnings weakening."
    action = "Monitor earnings forecasts closely."
    score = 0.5
    source_link = "FactSet / Bloomberg consensus data (placeholder)"

    if value <= -5.0:
        status = "Red"
        note = f"~{value:.0f}% net revisions. Widespread negative revisions; structural earnings risk is high."
        action = "Avoid highly cyclical/growth stocks until revisions stabilize."
        score = 1.0 
    elif value >= 0.0:
        status = "Green"
        note = f"~{value:.0f}% net revisions. Positive or neutral revisions; earnings are supporting the market."
        action = "No change."
        score = 0.0
    # value between 0.0 and -5.0 is Amber
        
    return {
        "name": "Earnings-revision breadth", 
        "status": status, 
        "note": note, 
        "source_link": source_link, 
        "action": action, 
        "score_value": score
        # Note: Add 'grade' and 'color' if they are used by your dashboard
    }

def score_leverage_yoy(value):
    """NEW: Margin Debt YoY Scoring (Macro Indicator - using N/A handling)."""
    
    # CRITICAL FIX: Handle "N/A" input and return the required 'score_value'
    if isinstance(value, str):
        return {
            "name": "Margin Debt YoY",
            "status": "N/A",
            "note": "Data N/A: Margin Debt YoY requires external data source.",
            "source_link": "FINRA Monthly Margin Statistics (placeholder)",
            "action": "Cannot score due to missing data.",
            "score_value": 0.0,  # <--- MUST BE 'score_value'
            "grade": 0
        }

    # Convert to float for comparison if it's a numeric string
    try:
        value = float(value)
    except ValueError:
        return {
            "name": "Margin Debt YoY",
            "status": "Error",
            "note": "Error: Margin Debt value could not be converted to number.",
            "source_link": "Error",
            "action": "Cannot score due to data error.",
            "score_value": 0.0,
            "grade": 0
        }
    
    # --- Actual Scoring Logic for numeric values ---
    if value > 30:
        score_value = 1.0  # Extreme leverage
        grade = -3
        note = f"~+{value:.0f}% YoY (Extreme leverage is building)."
        color = "red"
    elif value > 15:
        score_value = 0.75  # Elevated leverage
        grade = -2
        note = f"~+{value:.0f}% YoY proxies (elevated but not extreme)."
        color = "orange"
    elif value > 0:
        score_value = 0.5  # Modest increase
        grade = -1
        note = f"~+{value:.0f}% YoY proxies (modest increase)."
        color = "yellow"
    else:
        score_value = 0.0  # No growth or shrinking
        grade = 1
        note = f"~{value:.0f}% YoY (Shrinking or flat leverage)."
        color = "green"

    return {"name": "Margin Debt YoY", "value": value, "score_value": score_value, "grade": grade, "note": note, "color": color, "source_link": "FINRA Monthly Margin Statistics (placeholder)", "action": "Score"}

    # --- Actual Scoring Logic for numeric values ---
    if value > 30:
        score = 85  # Extreme leverage
        grade = -3
        note = f"~+{value:.0f}% YoY (Extreme leverage is building)."
        color = "red"
    elif value > 15:
        score = 65  # Elevated leverage
        grade = -2
        note = f"~+{value:.0f}% YoY proxies (elevated but not extreme)."
        color = "orange"
    elif value > 0:
        score = 50  # Modest increase
        grade = -1
        note = f"~+{value:.0f}% YoY proxies (modest increase)."
        color = "yellow"
    else:
        score = 30  # No growth or shrinking
        grade = 1
        note = f"~{value:.0f}% YoY (Shrinking or flat leverage)."
        color = "green"

    return {"value": value, "score": score, "grade": grade, "note": note, "color": color}

def score_bank_cds(value):
    """NEW: Bank CDS / financial stress Scoring (Micro Indicator)."""
    
    # CRITICAL FIX: Handle "N/A" and other string inputs to prevent KeyError
    if isinstance(value, str):
        return {
            "name": "Bank CDS / financial stress", 
            "status": "N/A", 
            "note": "Data N/A: Bank CDS data requires external API.", 
            "source_link": "Credit Default Swaps / Financial Stress Index (placeholder)", 
            "action": "Cannot score due to missing data.", 
            "score_value": 0.0, # Neutral score to allow sorting
            "grade": 0 # Assuming 'grade' is also used elsewhere, set to neutral
        }

    # Convert to float for comparison if it was a numeric string before this check
    try:
        value = float(value)
    except ValueError:
        # Fallback if the string wasn't "N/A" but still failed conversion
        return {
            "name": "Bank CDS / financial stress", 
            "status": "Error", 
            "note": "Error: Bank CDS value could not be converted to number.", 
            "source_link": "Error", 
            "action": "Cannot score due to data error.", 
            "score_value": 0.0,
            "grade": 0
        }

    # --- Scoring Logic for numeric values ---
    status = "Amber"
    note = f"Bank stress proxies mildly elevated at {value:.0f} basis."
    action = "Monitor credit spreads closely."
    score = 0.5
    source_link = "Credit Default Swaps / Financial Stress Index (placeholder)"

    if value >= 90.0:
        status = "Red"
        note = f"Bank stress proxies highly elevated at {value:.0f} basis. Systemic concern is rising."
        action = "Avoid non-core financial sector exposure; favour large, systemically important institutions (too big to fail)."
        score = 1.0 
    elif value <= 75.0:
        status = "Green"
        note = f"Bank stress proxies low at {value:.0f} basis. Stable financial conditions."
        action = "No change."
        score = 0.0
    # 75.0 < value < 90.0 is Amber
        
    return {
        "name": "Bank CDS / financial stress", 
        "status": status, 
        "note": note, 
        "source_link": source_link, 
        "action": action, 
        "score_value": score
        # Note: Add 'grade' and 'color' if they are used by your dashboard
    }
def score_consumer_delinquencies(value):
    """NEW: Consumer delinquencies (30-day) Scoring (Micro Indicator)."""
    
    # CRITICAL FIX: Handle "N/A" and other string inputs
    if isinstance(value, str):
        return {
            "name": "Consumer delinquencies (30-day)", 
            "status": "N/A", 
            "note": "Data N/A: Delinquency data requires external API.", 
            "source_link": "NY Fed Consumer Credit Panel / credit card data (placeholder)", 
            "action": "Cannot score due to missing data.", 
            "score_value": 0.0, # Neutral score to allow sorting
            "grade": 0 # Assuming 'grade' is also used elsewhere, set to neutral
        }

    # Convert to float for comparison if it was a numeric string before this check
    try:
        value = float(value)
    except ValueError:
        # Fallback if the string wasn't "N/A" but still failed conversion
        return {
            "name": "Consumer delinquencies (30-day)", 
            "status": "Error", 
            "note": "Error: Delinquency value could not be converted to number.", 
            "source_link": "Error", 
            "action": "Cannot score due to data error.", 
            "score_value": 0.0,
            "grade": 0
        }

    # --- Scoring Logic for numeric values ---
    status = "Green"
    note = f"~{value:.1f}% — household delinquencies not yet critical."
    action = "Current level is low; no immediate action required."
    score = 0.0
    source_link = "NY Fed Consumer Credit Panel / credit card data (placeholder)"

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
        
    return {"name": "Geopolitical (China/Russia/region)", "status": status, "note": note, "source_link": "Manual Qualitative Assessment", "action": action, "score_value": score}


def generate_narrative(score, overall_status, top_triggers, MAX_SCORE):
    """
    Generates a short summary and the full daily narrative based on the final score.
    
    NOTE: This is placeholder logic. Replace with your actual detailed, score-based narrative.
    """
    
    date_str = datetime.datetime.now().strftime("%A, %B %d, %Y")
    
    if score > 12.0: # FULL-STORM
        narrative_summary = "Atlas remains at **FULL-STORM** risk. This is a critical liquidity posture driven by extreme VIX, credit spreads, and ongoing fiscal uncertainty. The primary mandate is maximum capital preservation and liquidity."
        full_narrative = (
            f"**Daily Atlas Analysis: FULL-STORM ({score:.1f}/{MAX_SCORE:.1f}) | {date_str}**\n\n"
            "The system is under maximum stress. With the Composite Score exceeding 12.0, "
            "we are flagging acute systemic risk. The core drivers are the sustained spike in VIX and HY OAS, "
            "indicating a simultaneous breakdown in implied volatility and credit market functioning. "
            "This combination suggests a broad institutional de-risking and a 'dash for cash' phenomenon.\n\n"
            "**Key Action:** All capital must be positioned defensively. Liquidity is the priority. "
            "The market is highly vulnerable to a sudden, non-linear shock. Do not attempt tactical equity buys. "
            f"Top triggers: {', '.join(top_triggers)}."
        )
    elif score > 8.0: # SEVERE RISK
        narrative_summary = f"**SEVERE RISK** posture confirmed. The market is under high, persistent pressure driven primarily by long-term yield pricing and equity fragility. The focus remains on hedging duration and monitoring market internals."
        full_narrative = (
            f"**Daily Atlas Analysis: SEVERE RISK ({score:.1f}/{MAX_SCORE:.1f}) | {date_str}**\n\n"
            "Global markets are exhibiting high risk, with the core composite holding above 8.0. "
            "The macro picture is dominated by the repricing of long-term rates (30Y Yield), reflecting deep concern over U.S. fiscal dominance and structural inflation. "
            "This macro pressure is feeding into micro fragility, specifically seen in the small-cap underperformance and rising earnings-revision breadth concerns.\n\n"
            "**Key Action:** This is a Storm Posture. Aggressively limit duration exposure and maintain protective equity hedges. "
            "The market is sensitive to any negative news flow, especially concerning US fiscal policy or unexpected central bank moves. "
            f"Top triggers: {', '.join(top_triggers)}."
        )
    elif score > 4.0: # ELEVATED RISK
        narrative_summary = f"**ELEVATED RISK** remains in place. Key volatility and FX triggers are active, warranting caution. Maintain defensive positioning and monitor micro-indicators for stabilization."
        full_narrative = (
            f"**Daily Atlas Analysis: ELEVATED RISK ({score:.1f}/{MAX_SCORE:.1f}) | {date_str}**\n\n"
            "The risk environment is elevated but contained. While the majority of triggers are in the 'Amber' band, "
            "the sustained VIX and AUDUSD weakness suggest a tentative global risk appetite. This environment allows for flexibility but demands vigilance.\n\n"
            "**Key Action:** Maintain protective hedges. The focus should be on liquidity management and avoiding new high-beta positions. "
            "The key to de-risking will be a sustained drop in the VIX below 18.0 and a stabilization in the Funding Spread (SOFR–OIS). "
            f"Top triggers: {', '.join(top_triggers)}."
        )
    else: # MONITOR (GREEN)
        narrative_summary = f"**MONITOR (GREEN)** posture. The risk environment is favorable; only minor, isolated triggers are active. Favour moderate risk-on positioning."
        full_narrative = (
            f"**Daily Atlas Analysis: MONITOR (GREEN) ({score:.1f}/{MAX_SCORE:.1f}) | {date_str}**\n\n"
            "A benign environment prevails. With the composite score below 4.0, the core macro engine is stable. "
            "Low volatility and stable credit spreads suggest ample liquidity and normalized market function.\n\n"
            "**Key Action:** Favour risk-on positioning, but maintain discipline. The current low-risk environment is ideal for adding to core equity and credit holdings. "
            "Watch for early warning signs in the Geopolitical and Earnings Revision indicators."
        )
        
    return narrative_summary, full_narrative.strip()


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


# --- MAIN EXECUTION ---
if __name__ == "__main__":
    get_all_indicators()