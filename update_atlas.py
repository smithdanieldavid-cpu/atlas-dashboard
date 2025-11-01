import json
import datetime
import random 
import requests 

# --- CONFIGURATION ---

# 1. Output File Path (Must match your front-end fetch)
OUTPUT_FILE = "data/atlas-latest.json" 

# 2. API Keys and Endpoints (Placeholder structure)
# WARNING: Store real keys securely (e.g., environment variables)
API_CONFIG = {
    "FRED_API_KEY": "YOUR_FRED_KEY_HERE",
    "VIX_ENDPOINT": "YOUR_VIX_API_ENDPOINT", 
    "GOLD_ENDPOINT": "YOUR_GOLD_API_ENDPOINT",
    "HYOAS_ENDPOINT": "YOUR_HYOAS_API_ENDPOINT", 
    "FRED_3YR_ID": "GS3",
    "FRED_30YR_ID": "GS30",
    "FX_ENDPOINT": "YOUR_FX_API_ENDPOINT", 
    "WTI_ENDPOINT": "YOUR_WTI_API_ENDPOINT",
}

# --- 1. DATA FETCHING AND PARSING FUNCTIONS ---

def fetch_indicator_data(indicator_id):
    """
    Placeholder function for API calls. 
    REPLACE this with actual API fetching logic using the 'requests' library.
    """
    
    # Macro Indicators
    if indicator_id == "VIX":
        return random.uniform(19.5, 24.5) 
    
    elif indicator_id == "10Y_YIELD":
        return random.uniform(3.8, 4.8)
    
    elif indicator_id == "3Y_YIELD":
        return random.uniform(3.20, 3.80) 
        
    elif indicator_id == "30Y_YIELD":
        return random.uniform(4.10, 4.50) 
    
    elif indicator_id == "GOLD_PRICE":
        return random.uniform(1900.00, 2150.00) 
        
    elif indicator_id == "EURUSD":
        return random.uniform(1.10, 1.18) 
        
    elif indicator_id == "WTI_CRUDE":
        return random.uniform(65.0, 95.0) 

    # Micro Indicators
    elif indicator_id == "HY_OAS":
        return random.uniform(340.0, 420.0) 

    return None


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


# --- 3. COMPILATION AND SCORING ---

def get_all_indicators():
    """Fetches and scores all Macro and Micro indicators."""
    
    # --- 1. Fetch Raw Data ---
    raw_vix = fetch_indicator_data("VIX")
    raw_3yr = fetch_indicator_data("3Y_YIELD")
    raw_10yr = fetch_indicator_data("10Y_YIELD")
    raw_30yr = fetch_indicator_data("30Y_YIELD")
    raw_gold = fetch_indicator_data("GOLD_PRICE")
    raw_eurusd = fetch_indicator_data("EURUSD")
    raw_wti = fetch_indicator_data("WTI_CRUDE") # <-- NEW
    raw_hy_oas = fetch_indicator_data("HY_OAS")
    
    # --- 2. Score Indicators ---
    vix_result = score_vix(raw_vix)
    yield_3yr_result = score_3yr_yield(raw_3yr)
    yield_10yr_result = score_10yr_yield(raw_10yr)
    yield_30yr_result = score_30yr_yield(raw_30yr)
    gold_result = score_gold(raw_gold)
    eurusd_result = score_eurusd(raw_eurusd)
    wti_result = score_wti_crude(raw_wti) # <-- NEW
    hy_oas_result = score_hy_oas(raw_hy_oas)
    
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
        wti_result, # <-- NEW
        shutdown_result,
        # ... add all other macro results here ...
    ]
    
    micro_list = [
        hy_oas_result,
        # ... other micro results ...
    ]

    total_macro_score = sum(r.get("score_value", 0) for r in macro_list)
    total_micro_score = sum(r.get("score_value", 0) for r in micro_list)
    
    # Apply your weighting: Micro indicators contribute 0.5 points to the total score
    composite_score = total_macro_score + (total_micro_score * 0.5) 
    MAX_SCORE = 8.0 # Define your max possible score (update as you add more indicators)

    return macro_list, micro_list, composite_score, MAX_SCORE


# --- 4. JSON GENERATION ---

def generate_atlas_json():
    
    macro_data, micro_data, score, max_score = get_all_indicators()

    # Determine Overall Status based on score
    if score >= 6.0:
        overall_status = "FULL-STORM"
        comment = "Macro triggers are dominant — maintain highly defensive posture."
    elif score >= 4.0:
        overall_status = "SEVERE RISK"
        comment = "Macro triggers rising — increase liquidity and hedges."
    else:
        overall_status = "ELEVATED RISK"
        comment = "Monitored triggers are active — proceed with caution."


    # Construct the final JSON dictionary
    data = {
        "overall": {
            "date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
            "status": overall_status,
            "score": score,
            "max_score": max_score,
            "comment": comment,
            "composite_summary": f"Composite effective triggers ≈ {score:.1f} / {max_score:.1f} → {overall_status} posture confirmed."
        },
        "macro": [
            {k: v for k, v in item.items() if k != 'score_value'} for item in macro_data
        ],
        "micro": [
            {k: v for k, v in item.items() if k != 'score_value'} for item in micro_data
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
            {"name": "SOFR–OIS", "note": ">45 bps (funding stress)."}
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
    generate_atlas_json()