from datetime import datetime

# ==========================================
# Badee Binance Scanner
# Data Profile Engine V2.3 (Build 1)
# Official Architecture API - LOCKED
# ==========================================

REQUIRED_INDICATORS = [

    "EMA9",
    "EMA20",
    "EMA21",
    "EMA50",

    "RSI",
    "ATR",
    "ADX",

    "VWAP",
    "Momentum5",

    "VolumeSpike",
    "EMA20_Slope",
    "DistanceEMA20",

    "CandleStrength"

]


# ==========================================
# Analyze One DataFrame
# ==========================================

def analyze_dataframe(df):

    bars = len(df)

    available = df.attrs.get(
        "available_indicators",
        []
    )

    quality = float(

        df.attrs.get(

            "indicator_quality",

            0

        )

    )

    missing = [

        indicator

        for indicator in REQUIRED_INDICATORS

        if indicator not in available

    ]


    if quality >= 95:

        status = "FULL"

        trade_mode = "FULL_ANALYSIS"

        confidence_limit = 98


    elif quality >= 75:

        status = "PARTIAL"

        trade_mode = "PARTIAL_ANALYSIS"

        confidence_limit = 90


    elif quality >= 50:

        status = "LIMITED"

        trade_mode = "PARTIAL_ANALYSIS"

        confidence_limit = 80


    else:

        status = "NEW"

        trade_mode = "NEW_LISTING"

        confidence_limit = 70


    return {

        "bars": bars,

        "quality": quality,

        "status": status,

        "trade_mode": trade_mode,

        "confidence_limit": confidence_limit,

        "available": available,

        "missing": missing

    }


# ==========================================
# Analyze All Timeframes
# ==========================================

def analyze_data_profile(

    df_15m,

    df_1h,

    df_4h

):

    p15 = analyze_dataframe(df_15m)

    p1h = analyze_dataframe(df_1h)

    p4h = analyze_dataframe(df_4h)


    overall_quality = round(

        (

            p15["quality"]

            +

            p1h["quality"]

            +

            p4h["quality"]

        ) / 3,

        1

    )


    statuses = [

        p15["status"],

        p1h["status"],

        p4h["status"]

    ]


    if all(

        status == "FULL"

        for status in statuses

    ):

        overall_status = "FULL"


    elif "NEW" in statuses:

        overall_status = "NEW"


    elif "LIMITED" in statuses:

        overall_status = "LIMITED"


    else:

        overall_status = "PARTIAL"


    if overall_status == "FULL":

        trade_mode = "FULL_ANALYSIS"

    elif overall_status in ["PARTIAL", "LIMITED"]:

        trade_mode = "PARTIAL_ANALYSIS"

    else:

        trade_mode = "NEW_LISTING"


    # ==========================================
    # Dynamic Confidence Limit (Overall Quality Based)
    # ==========================================

    if overall_quality >= 95:

        confidence_limit = 98

    elif overall_quality >= 85:

        confidence_limit = 95

    elif overall_quality >= 75:

        confidence_limit = 90

    elif overall_quality >= 60:

        confidence_limit = 85

    else:

        confidence_limit = 70


    # ==========================================
    # System-wide Health Score Calculation
    # ==========================================

    health_score = round(

        overall_quality

        *

        (

            confidence_limit / 100

        ),

        1

    )


    # ==========================================
    # System-wide Available Indicators
    # ==========================================

    overall_available = sorted(

        set(

            p15["available"]

            +

            p1h["available"]

            +

            p4h["available"]

        )

    )


    return {

        "profile_version": "2.3",

        "build": 1,

        "generated_at": datetime.utcnow().isoformat() + "Z",

        "engine": {

            "indicator_engine": "V2",

            "profile_engine": "V2.3"

        },

        "analysis": {

            "engine": "SCORE_V5",

            "version": "5.0",

            "mode": trade_mode,

            "allow_override": False

        },

        "compatible_with": {

            "score_engine": "V5",

            "decision_engine": "V1",

            "indicator_engine": "V2"

        },

        "status": overall_status,

        "trade_mode": trade_mode,

        "quality": overall_quality,

        "confidence_limit": confidence_limit,

        "health_score": health_score,

        "overall_available": overall_available,

        "available_indicators": {

            "15M": p15["available"],

            "1H": p1h["available"],

            "4H": p4h["available"]

        },

        "15M": p15,

        "1H": p1h,

        "4H": p4h

    }