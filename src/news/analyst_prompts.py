"""Template-based 'If I were an analyst' prompts.

No LLM required - uses structured templates based on event type.
"""

from typing import Dict, Any, List, Optional


# Earnings analysis templates
EARNINGS_TEMPLATES = {
    "default": {
        "title": "📊 If I Were an Analyst: {ticker} Earnings",
        "questions": [
            "1. **Revenue Quality**: Was growth organic or acquisition-driven?",
            "2. **Margin Trajectory**: Are operating margins expanding or compressing?",
            "3. **Guidance Signal**: Did management raise, maintain, or lower guidance?",
            "4. **Segment Mix**: Which business units are driving results?"
        ],
        "checklist": [
            "☐ Compare EPS beat/miss to whisper numbers",
            "☐ Review guidance vs. consensus",
            "☐ Check for one-time items affecting results",
            "☐ Evaluate management tone on call"
        ]
    },
    "beat": {
        "title": "📈 Earnings Beat: {ticker}",
        "questions": [
            "1. **Sustainability**: Is this beat repeatable or one-time?",
            "2. **Street Reaction**: Are estimates being revised up?",
            "3. **Multiple Implications**: Does this justify current valuation?",
            "4. **Guidance Quality**: Did guidance beat as much as results?"
        ],
        "checklist": [
            "☐ Check magnitude of beat vs. normal variance",
            "☐ Review guidance vs. new consensus",
            "☐ Look for analyst upgrades",
            "☐ Assess buy-the-dip vs. trap risk"
        ]
    },
    "miss": {
        "title": "📉 Earnings Miss: {ticker}",
        "questions": [
            "1. **Nature of Miss**: Temporary headwind or structural issue?",
            "2. **Management Response**: Is there a credible turnaround plan?",
            "3. **Balance Sheet Impact**: Does this strain liquidity or covenants?",
            "4. **Competitive Position**: Is market share at risk?"
        ],
        "checklist": [
            "☐ Identify root cause of miss",
            "☐ Assess guidance credibility",
            "☐ Check for buying opportunity vs. value trap",
            "☐ Review analyst downgrades"
        ]
    }
}


# Macro event analysis templates
MACRO_TEMPLATES = {
    "FOMC": {
        "title": "🏦 FOMC Analysis",
        "questions": [
            "1. **Rate Path**: How has the dot plot shifted?",
            "2. **QT Pace**: Any changes to balance sheet policy?",
            "3. **Inflation View**: Are they more hawkish or dovish?",
            "4. **Labor Market**: How do they characterize employment?"
        ],
        "checklist": [
            "☐ Compare statement to previous meeting",
            "☐ Note any dissenting votes",
            "☐ Track fed funds futures reaction",
            "☐ Assess sector implications"
        ]
    },
    "CPI": {
        "title": "📊 CPI Analysis",
        "questions": [
            "1. **Core vs. Headline**: What's driving the divergence?",
            "2. **Shelter Component**: Is rent inflation peaking?",
            "3. **Services Inflation**: What's the stickiness risk?",
            "4. **Fed Implications**: Does this change rate expectations?"
        ],
        "checklist": [
            "☐ Break down by category",
            "☐ Compare to Cleveland Fed Nowcast",
            "☐ Assess real yield implications",
            "☐ Check Treasury reaction"
        ]
    },
    "JOBS": {
        "title": "👷 Jobs Report Analysis",
        "questions": [
            "1. **Payroll Quality**: Full-time vs. part-time composition?",
            "2. **Wage Growth**: Is it above productivity growth?",
            "3. **Participation Rate**: Any hidden slack?",
            "4. **Sector Trends**: Where are gains/losses concentrated?"
        ],
        "checklist": [
            "☐ Watch for revisions to prior months",
            "☐ Compare to ADP and JOLTS",
            "☐ Assess Fed reaction function",
            "☐ Consider sector implications"
        ]
    },
    "default": {
        "title": "📰 Macro Event Analysis",
        "questions": [
            "1. **Market Impact**: How is this priced into expectations?",
            "2. **Policy Implications**: Does this change Fed/fiscal trajectory?",
            "3. **Sector Effects**: Who are the winners and losers?",
            "4. **Duration**: Is this a short-term or persistent shift?"
        ],
        "checklist": [
            "☐ Compare to consensus expectations",
            "☐ Assess cross-asset implications",
            "☐ Review historical analogs",
            "☐ Monitor follow-through"
        ]
    }
}


# AI/tech development templates
AI_TEMPLATES = {
    "model_release": {
        "title": "🤖 AI Model Analysis",
        "questions": [
            "1. **Capability Jump**: What new capabilities does this unlock?",
            "2. **Cost Structure**: How does it affect inference economics?",
            "3. **Competitive Impact**: Who gains/loses market position?",
            "4. **Adoption Curve**: What's the path to revenue?"
        ],
        "checklist": [
            "☐ Compare to existing models (benchmarks)",
            "☐ Assess compute requirements",
            "☐ Identify enterprise use cases",
            "☐ Consider regulatory implications"
        ]
    },
    "default": {
        "title": "🤖 AI/Tech Development Analysis",
        "questions": [
            "1. **Strategic Significance**: Is this incremental or transformative?",
            "2. **TAM Impact**: Does this expand addressable market?",
            "3. **Competitive Moat**: How defensible is this advantage?",
            "4. **Investment Implications**: Who benefits in the value chain?"
        ],
        "checklist": [
            "☐ Identify public company exposure",
            "☐ Assess infrastructure needs",
            "☐ Consider regulatory risk",
            "☐ Review sell-side reactions"
        ]
    }
}


# Valuation lens templates
VALUATION_TEMPLATES = {
    "revenue": {
        "impact": "Revenue Driver",
        "emoji": "💰",
        "description": "This primarily affects top-line growth expectations.",
        "metrics": ["Revenue growth rate", "TAM expansion", "Market share"]
    },
    "margin": {
        "impact": "Margin Effect",
        "emoji": "📊",
        "description": "This impacts profitability and operating leverage.",
        "metrics": ["Gross margin", "Operating margin", "EBITDA margin"]
    },
    "discount_rate": {
        "impact": "Discount Rate",
        "emoji": "📉",
        "description": "This changes the cost of capital and risk premium.",
        "metrics": ["WACC", "Risk-free rate", "Equity risk premium"]
    },
    "multiple": {
        "impact": "Multiple Expansion/Compression",
        "emoji": "🔢",
        "description": "This affects how the market values earnings/sales.",
        "metrics": ["P/E ratio", "EV/EBITDA", "P/S ratio"]
    }
}


# Finance concept mapping
CLASSROOM_CONCEPTS = {
    "FOMC": ["CAPM", "risk-free rate", "discount rate", "term structure"],
    "CPI": ["real returns", "inflation expectations", "TIPS", "nominal vs real"],
    "JOBS": ["Phillips curve", "Okun's law", "labor economics"],
    "earnings": ["DCF valuation", "comparable analysis", "multiple valuation"],
    "AI": ["growth investing", "option value", "real options", "disruption"]
}


def get_analyst_prompt(
    event_type: str,
    category: str,
    ticker: Optional[str] = None,
    sub_type: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get the appropriate analyst prompt template.
    
    Args:
        event_type: Type of event (e.g., "FOMC", "CPI", "earnings")
        category: Category ("ai", "macro", "earnings")
        ticker: Ticker symbol if applicable
        sub_type: Sub-type (e.g., "beat", "miss" for earnings)
    
    Returns:
        Dict with title, questions, and checklist.
    """
    if category == "earnings":
        template = EARNINGS_TEMPLATES.get(sub_type or "default", EARNINGS_TEMPLATES["default"])
    elif category == "macro":
        template = MACRO_TEMPLATES.get(event_type, MACRO_TEMPLATES["default"])
    elif category == "ai":
        if "model" in (event_type or "").lower() or "release" in (event_type or "").lower():
            template = AI_TEMPLATES["model_release"]
        else:
            template = AI_TEMPLATES["default"]
    else:
        template = AI_TEMPLATES["default"]
    
    # Format with ticker if provided
    result = {
        "title": template["title"].format(ticker=ticker or "Event"),
        "questions": template["questions"],
        "checklist": template["checklist"]
    }
    
    return result


def get_valuation_lens(
    event_type: str,
    category: str,
    rate_action: Optional[str] = None,
    earnings_type: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get valuation impact classification.
    
    Args:
        event_type: Type of event
        category: Event category
        rate_action: "hike", "cut", or "hold" for FOMC
        earnings_type: "beat" or "miss" for earnings
    
    Returns:
        Valuation lens with impact type and description.
    """
    # Determine primary valuation driver
    if category == "macro":
        if event_type in ("FOMC", "FED_SPEECH"):
            impact = "discount_rate"
        elif event_type in ("CPI", "PCE"):
            impact = "discount_rate"
        elif event_type in ("JOBS", "GDP"):
            impact = "revenue"
        else:
            impact = "multiple"
    elif category == "earnings":
        if earnings_type == "beat":
            impact = "revenue"
        elif earnings_type == "miss":
            impact = "margin"
        else:
            impact = "multiple"
    elif category == "ai":
        impact = "revenue"  # AI news typically about growth
    else:
        impact = "multiple"
    
    template = VALUATION_TEMPLATES[impact]
    
    return {
        "impact_type": template["impact"],
        "emoji": template["emoji"],
        "description": template["description"],
        "key_metrics": template["metrics"]
    }


def get_classroom_bridge(
    event_type: str,
    category: str
) -> Dict[str, Any]:
    """
    Get classroom concept mapping.
    
    Maps the event to relevant finance concepts.
    """
    # Find matching concepts
    concepts = []
    
    if category == "macro":
        concepts = CLASSROOM_CONCEPTS.get(event_type, [])
    elif category == "earnings":
        concepts = CLASSROOM_CONCEPTS.get("earnings", [])
    elif category == "ai":
        concepts = CLASSROOM_CONCEPTS.get("AI", [])
    
    if not concepts:
        concepts = ["fundamental analysis", "market efficiency"]
    
    return {
        "concepts": concepts,
        "description": f"Related to: {', '.join(concepts)}"
    }


def format_analyst_message(
    item: Dict[str, Any]
) -> str:
    """
    Format a complete analyst prompt message for Discord.
    
    Args:
        item: News item with category, event type, etc.
    
    Returns:
        Formatted string for Discord embed description.
    """
    category = item.get("category", "general")
    event_type = item.get("macro_event_type", "")
    ticker = ", ".join(item.get("tickers", [])) if item.get("tickers") else None
    sub_type = item.get("earnings_type")
    
    prompt = get_analyst_prompt(event_type, category, ticker, sub_type)
    
    lines = []
    lines.append("**Questions to Answer:**")
    lines.extend(prompt["questions"])
    lines.append("")
    lines.append("**Checklist:**")
    lines.extend(prompt["checklist"])
    
    return "\n".join(lines)


def format_valuation_message(item: Dict[str, Any]) -> str:
    """Format valuation lens message for Discord."""
    category = item.get("category", "general")
    event_type = item.get("macro_event_type", "")
    rate_action = item.get("rate_info", {}).get("action")
    earnings_type = item.get("earnings_type")
    
    lens = get_valuation_lens(event_type, category, rate_action, earnings_type)
    
    lines = [
        f"{lens['emoji']} **{lens['impact_type']}**",
        "",
        lens["description"],
        "",
        "**Key Metrics to Watch:**"
    ]
    
    for metric in lens["key_metrics"]:
        lines.append(f"• {metric}")
    
    return "\n".join(lines)
