"""
Intent Detector for Contextual Chat Intelligence

Analyzes user messages to identify when they're referencing personal fitness data.
Uses keyword/pattern matching for fast detection with fallback to LLM for ambiguous cases.
"""

import re
from enum import Enum
from typing import Tuple, List, Optional
from dataclasses import dataclass


class IntentType(Enum):
    """Categories of user intent that require context injection."""
    NONE = "none"                    # General chat, no context needed
    RECENT_ACTIVITY = "recent_activity"  # References recent workout
    FATIGUE_RECOVERY = "fatigue_recovery"  # Tired, recovery, overtraining
    PERFORMANCE_REVIEW = "performance_review"  # Progress, improvement questions
    SPECIFIC_METRIC = "specific_metric"  # VO2 max, pace, etc.
    COMPARISON = "comparison"        # Year-over-year, vs usual
    CHART_REQUEST = "chart_request"  # Graph/plot requests


@dataclass
class DetectedIntent:
    """Result of intent detection."""
    intent_type: IntentType
    confidence: float  # 0.0 to 1.0
    matched_keywords: List[str]
    activity_type_hint: Optional[str] = None  # running, hiking, etc.
    time_reference: Optional[str] = None  # today, yesterday, this week
    specific_date: Optional[str] = None  # YYYY-MM-DD if a specific date was mentioned


# Keyword patterns for each intent type
INTENT_PATTERNS = {
    IntentType.RECENT_ACTIVITY: {
        "keywords": [
            "my run", "my hike", "my workout", "my activity",
            "that run", "that hike", "that workout",
            "today's run", "today's workout", "yesterday's",
            "last run", "last hike", "last workout",
            "this morning", "this afternoon", "earlier today",
            "just finished", "just did", "just completed",
            "how did i do", "how did i look", "how was my"
        ],
        "patterns": [
            r"my (?:run|hike|walk|workout|ride|swim|activity)",
            r"(?:today's|yesterday's|this morning's) (?:run|workout|hike)",
            r"(?:last|recent|latest) (?:run|workout|hike|activity)",
            r"just (?:finished|did|completed) (?:a|my)?",
            r"how (?:did|was) (?:my|the|that)"
        ]
    },
    IntentType.FATIGUE_RECOVERY: {
        "keywords": [
            "tired", "exhausted", "worn out", "fatigued",
            "overtraining", "overtrained", "burnt out", "burned out",
            "recovery", "recovering", "rest", "resting",
            "sore", "soreness", "aching", "hurting",
            "feeling off", "not feeling", "feeling down",
            "energy", "low energy", "no energy",
            "sick", "getting sick", "coming down with",
            "sleep", "sleeping", "insomnia", "can't sleep"
        ],
        "patterns": [
            r"feel(?:ing)? (?:tired|exhausted|worn|fatigued|off|down)",
            r"(?:low|no|lacking) energy",
            r"over(?:training|worked|did it)",
            r"need(?:ing)? (?:rest|recovery|a break)"
        ]
    },
    IntentType.PERFORMANCE_REVIEW: {
        "keywords": [
            "how am i doing", "how'm i doing", "how i'm doing",
            "progress", "progressing", "improvement", "improving",
            "getting better", "getting faster", "getting stronger",
            "fitness level", "my fitness", "in shape",
            "on track", "goal", "goals", "training plan"
        ],
        "patterns": [
            r"(?:how|am) i (?:doing|progressing|improving)",
            r"(?:my|overall) (?:progress|improvement|fitness)",
            r"getting (?:better|faster|stronger|fitter)"
        ]
    },
    IntentType.SPECIFIC_METRIC: {
        "keywords": [
            "vo2 max", "vo2max", "vo2", "max oxygen",
            "heart rate", "hr", "resting heart rate", "rhr",
            "hrv", "heart rate variability",
            "pace", "speed", "tempo",
            "cadence", "stride", "steps per minute",
            "elevation", "climbing", "vertical",
            "calories", "burned",
            "zones", "heart rate zones", "training zones",
            # Sleep-related for Phase 2
            "my sleep", "sleep data", "sleep quality", "sleep score",
            "how did i sleep", "sleeping"
        ],
        "patterns": [
            r"(?:my|current|latest) (?:vo2|pace|hr|hrv|rhr|sleep)",
            r"(?:what|where) (?:is|are) my (?:zones|pace|hr|sleep)",
            r"how (?:did|was|am) i sleep(?:ing)?"
        ]
    },
    IntentType.COMPARISON: {
        "keywords": [
            "compared to", "compare", "comparison",
            "vs", "versus", "against",
            "last year", "this time last year", "year over year",
            "last month", "last week", "usual", "normal", "average"
        ],
        "patterns": [
            r"compare(?:d)? (?:to|with|vs)",
            r"(?:better|worse|faster|slower|more|less) than (?:last|usual|normal)",
            r"year (?:over|vs) year"
        ]
    },
    IntentType.CHART_REQUEST: {
        "keywords": [
            "graph", "chart", "plot", "visualize", "show me a graph",
            "show me a chart", "trend", "trends", "progression"
        ],
        "patterns": [
            r"(?:graph|chart|plot|visualize) (?:my|the)",
            r"show (?:me)? (?:a|the) (?:graph|chart|plot)",
            r"(?:pace|hr|hrv|distance) (?:trend|progression|over time)"
        ]
    }
}

# Activity type detection
ACTIVITY_KEYWORDS = {
    "running": ["run", "running", "jog", "jogging", "sprint", "race", "marathon", "5k", "10k"],
    "hiking": ["hike", "hiking", "trail", "mountain", "climb"],
    "cycling": ["ride", "riding", "bike", "biking", "cycling", "cycle"],
    "swimming": ["swim", "swimming", "pool", "laps"],
    "walking": ["walk", "walking", "steps"],
    "strength": ["lift", "lifting", "weights", "gym", "strength", "workout"]
}

# Time reference detection
TIME_PATTERNS = {
    "today": [r"\btoday\b", r"this morning", r"this afternoon", r"this evening", r"earlier today"],
    "yesterday": [r"\byesterday\b", r"last night"],
    "this_week": [r"this week", r"past few days", r"lately", r"recently"],
    "last_week": [r"last week"],
    "this_month": [r"this month"],
    "recent": [r"\blast\b", r"\brecent\b", r"\blatest\b", r"just (?:did|finished|completed)"]
}

# Day of week patterns
DAY_OF_WEEK_PATTERNS = {
    "monday": [r"\bmonday\b", r"\bmon\b"],
    "tuesday": [r"\btuesday\b", r"\btue\b", r"\btues\b"],
    "wednesday": [r"\bwednesday\b", r"\bwed\b"],
    "thursday": [r"\bthursday\b", r"\bthu\b", r"\bthurs\b"],
    "friday": [r"\bfriday\b", r"\bfri\b"],
    "saturday": [r"\bsaturday\b", r"\bsat\b"],
    "sunday": [r"\bsunday\b", r"\bsun\b"]
}

# Month patterns for specific date extraction
MONTH_NAMES = {
    "january": 1, "jan": 1, "february": 2, "feb": 2, "march": 3, "mar": 3,
    "april": 4, "apr": 4, "may": 5, "june": 6, "jun": 6,
    "july": 7, "jul": 7, "august": 8, "aug": 8, "september": 9, "sep": 9, "sept": 9,
    "october": 10, "oct": 10, "november": 11, "nov": 11, "december": 12, "dec": 12
}


def extract_specific_date(message: str) -> Optional[str]:
    """
    Extract a specific date from the message if mentioned.
    Returns date string in YYYY-MM-DD format or None.
    """
    from datetime import datetime, timedelta
    
    message_lower = message.lower()
    today = datetime.now()
    
    # Check for "today"
    if re.search(r"\btoday\b", message_lower):
        return today.strftime("%Y-%m-%d")
    
    # Check for "yesterday"
    if re.search(r"\byesterday\b", message_lower):
        return (today - timedelta(days=1)).strftime("%Y-%m-%d")
    
    # Check for day of week (e.g., "on Tuesday", "last Monday")
    for day_name, patterns in DAY_OF_WEEK_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, message_lower):
                # Find the most recent occurrence of that day
                day_index = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"].index(day_name)
                current_day = today.weekday()
                days_ago = (current_day - day_index) % 7
                
                # If days_ago is 0, it means today is that day
                # Check if user explicitly said "last" - if so, go back a week
                if days_ago == 0:
                    if re.search(rf"\blast\s+{day_name}", message_lower):
                        days_ago = 7  # Explicitly asked for "last Sunday"
                    # else: days_ago stays 0, meaning today
                
                target_date = today - timedelta(days=days_ago)
                return target_date.strftime("%Y-%m-%d")
    
    # Check for specific date patterns like "December 5", "Dec 5th", "12/5", "5th of December"
    # Pattern: Month Day (e.g., "December 5", "Dec 5th")
    for month_name, month_num in MONTH_NAMES.items():
        pattern = rf"{month_name}\.?\s+(\d{{1,2}})(?:st|nd|rd|th)?"
        match = re.search(pattern, message_lower)
        if match:
            day = int(match.group(1))
            year = today.year
            # If the date is in the future, assume last year
            try:
                target_date = datetime(year, month_num, day)
                if target_date > today:
                    target_date = datetime(year - 1, month_num, day)
                return target_date.strftime("%Y-%m-%d")
            except ValueError:
                pass
    
    # Pattern: "5th of December"
    match = re.search(r"(\d{1,2})(?:st|nd|rd|th)?\s+of\s+(\w+)", message_lower)
    if match:
        day = int(match.group(1))
        month_name = match.group(2)
        month_num = MONTH_NAMES.get(month_name)
        if month_num:
            year = today.year
            try:
                target_date = datetime(year, month_num, day)
                if target_date > today:
                    target_date = datetime(year - 1, month_num, day)
                return target_date.strftime("%Y-%m-%d")
            except ValueError:
                pass
    
    # Pattern: MM/DD or MM-DD
    match = re.search(r"(\d{1,2})[/\-](\d{1,2})(?:[/\-](\d{2,4}))?", message_lower)
    if match:
        month = int(match.group(1))
        day = int(match.group(2))
        year = int(match.group(3)) if match.group(3) else today.year
        if year < 100:
            year += 2000
        try:
            target_date = datetime(year, month, day)
            if target_date > today:
                target_date = datetime(year - 1, month, day)
            return target_date.strftime("%Y-%m-%d")
        except ValueError:
            pass
    
    return None


def detect_intent(message: str) -> DetectedIntent:
    """
    Analyze a user message and detect the primary intent.
    
    Args:
        message: The user's chat message
        
    Returns:
        DetectedIntent with type, confidence, and metadata
    """
    message_lower = message.lower()
    
    # Score each intent type
    intent_scores = {}
    matched_keywords_by_intent = {}
    
    for intent_type, patterns in INTENT_PATTERNS.items():
        score = 0
        matched = []
        
        # Check keywords
        for keyword in patterns["keywords"]:
            if keyword in message_lower:
                # Boost score for CHART_REQUEST to ensure it overrides SPECIFIC_METRIC
                if intent_type == IntentType.CHART_REQUEST:
                    score += 3
                else:
                    score += 1
                matched.append(keyword)
        
        # Check regex patterns (weighted higher)
        for pattern in patterns["patterns"]:
            if re.search(pattern, message_lower):
                score += 2
                matched.append(f"pattern:{pattern[:20]}...")
        
        intent_scores[intent_type] = score
        matched_keywords_by_intent[intent_type] = matched
    
    # Find the highest scoring intent
    best_intent = max(intent_scores.items(), key=lambda x: x[1])
    intent_type = best_intent[0]
    score = best_intent[1]
    
    # If no significant matches, return NONE
    if score < 1:
        return DetectedIntent(
            intent_type=IntentType.NONE,
            confidence=1.0,
            matched_keywords=[]
        )
    
    # Calculate confidence based on score
    # 1 match = 0.5, 2 matches = 0.7, 3+ matches = 0.9+
    confidence = min(0.5 + (score * 0.15), 0.95)
    
    # Detect activity type hint
    activity_type = None
    for act_type, keywords in ACTIVITY_KEYWORDS.items():
        for keyword in keywords:
            if keyword in message_lower:
                activity_type = act_type
                break
        if activity_type:
            break
    
    # Detect time reference
    time_ref = None
    for time_type, patterns in TIME_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, message_lower):
                time_ref = time_type
                break
        if time_ref:
            break
    
    # Extract specific date if mentioned
    specific_date = extract_specific_date(message)
    
    return DetectedIntent(
        intent_type=intent_type,
        confidence=confidence,
        matched_keywords=matched_keywords_by_intent[intent_type],
        activity_type_hint=activity_type,
        time_reference=time_ref or "recent",  # Default to recent
        specific_date=specific_date
    )


def needs_context(intent: DetectedIntent) -> bool:
    """Check if the detected intent requires context injection."""
    return intent.intent_type != IntentType.NONE and intent.confidence >= 0.5


def extract_chart_metric(message: str) -> str:
    """Determine the metric to chart from the user message."""
    msg_lower = message.lower()
    
    # Map keywords to metrics
    metrics = {
        "hrv": ["hrv", "recovery", "stress"],
        "distance": ["distance", "mileage", "volume", "how far"],
        "training_load": ["load", "training load", "effort"],
        "heart_rate": ["heart rate", "hr", "pulse", "bpm"],
        "cadence": ["cadence", "steps", "spm"],
        "elevation": ["elevation", "climbing", "ascent", "vertical"],
        "sleep_score": ["sleep score", "sleep quality", "sleep"],
        "pace": ["pace", "speed", "fast"]
    }
    
    for metric, keywords in metrics.items():
        if any(k in msg_lower for k in keywords):
            return metric
            
    return "pace" # Default


def detect_chart_scope(message: str) -> str:
    """
    Detect if the chart request is for a 'trend' (over time) or 'activity' (specific workout).
    Returns 'trend' or 'activity'.
    """
    msg_lower = message.lower()
    
    # Activity indicators
    activity_indicators = [
        "last run", "last activity", "last workout", "last hike", "last ride",
        "this run", "this activity", "this workout",
        "that run", "that activity", "that workout",
        "yesterday's run", "yesterday's workout",
        "run from", "activity from", "workout from",
        "my run", "my workout" # Ambiguous, but usually implies specific if singular
    ]
    
    if any(k in msg_lower for k in activity_indicators):
        return "activity"
        
    # Check for specific date mention which implies activity
    if extract_specific_date(message):
        return "activity"
    
    return "trend"
