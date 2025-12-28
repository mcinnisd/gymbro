"""
Analyzes user messages to identify when they're referencing personal fitness data.
Uses LLM-based detection for complex queries with a fast keyword fallback.
"""

import re
import json
import logging
from enum import Enum
from typing import Tuple, List, Optional, Dict, Any
from dataclasses import dataclass
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


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
    specific_date: Optional[str] = None  # YYYY-MM-DD
    start_date: Optional[str] = None  # YYYY-MM-DD
    end_date: Optional[str] = None  # YYYY-MM-DD
    metrics: List[str] = None        # pace, hrv, distance, etc.
    is_comparison: bool = False
    comparison_period: Optional[str] = None # last_year, previous_month
    is_chart_request: bool = False
    original_message: str = ""  # The full user message

    def __post_init__(self):
        if self.metrics is None:
            self.metrics = []


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
            "how did i do", "how did i look", "how was my",
            "past week", "last 7 days", "this past week"
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
            "on track", "goal", "goals", "training plan",
            "past week summary", "weekly review"
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
    "this_week": [r"this week", r"past few days", r"lately", r"recently", r"past week", r"last 7 days"],
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
        specific_date=specific_date,
        original_message=message
    )


def hybrid_detect_intent(message: str) -> DetectedIntent:
    """
    Optimized intent detection:
    1. Fast Regex/Keyword matching first.
    2. If confidence is high (>0.7), return immediately.
    3. Otherwise, use LLM for nuanced parsing.
    """
    # 1. Fast match
    fast_intent = detect_intent(message)
    
    # If it's a very clear keyword match or no intent at all
    if fast_intent.confidence > 0.7 or fast_intent.intent_type == IntentType.NONE:
        # Check for simple greetings/thanks which should be NONE but might have noise
        if len(message.split()) < 3 and fast_intent.intent_type == IntentType.NONE:
            return fast_intent
            
        # If it's a specific metric or activity mention that is very clear, we're done
        if fast_intent.confidence > 0.8:
            return fast_intent

    # 2. LLM Fallback for complex queries
    logger.info(f"Fast intent confidence low ({fast_intent.confidence}), falling back to LLM for: {message[:50]}...")
    return llm_detect_intent(message)


def llm_detect_intent(message: str) -> DetectedIntent:
    """
    Use a fast LLM to detect intent and extract structured parameters.
    """
    from app.utils.llm_utils import generate_chat_response
    
    today = datetime.now()
    today_str = today.strftime("%Y-%m-%d")
    dow = today.strftime("%A")
    
    prompt = f"""
    You are an intent detector for a fitness coaching app. 
    Analyze the user message and extract the following into a JSON object.
    
    User Message: "{message}"
    Today's Date: {today_str} ({dow})
    
    Required Fields:
    1. "intent": One of ["none", "recent_activity", "fatigue_recovery", "performance_review", "specific_metric", "comparison", "chart_request"]
    2. "confidence": 0.0 to 1.0
    3. "activity_type": One of ["running", "hiking", "cycling", "swimming", "walking", "strength", null]
    4. "time_reference": One of ["today", "yesterday", "this_week", "last_week", "this_month", "recent", "date_range", null]
    5. "start_date": "YYYY-MM-DD" or null
    6. "end_date": "YYYY-MM-DD" or null (same as start_date if single day)
    7. "metrics": List of strings like ["pace", "hrv", "rhr", "distance", "cadence", "elevation"] or []
    8. "is_comparison": boolean
    9. "comparison_period": "last_year", "previous_period", or null
    10. "is_chart_request": boolean
    
    Guidelines:
    - "none": General chat, greeting, or irrelevant to fitness data.
    - "recent_activity": Asking about a specific workout or recent training.
    - "fatigue_recovery": Asking about tiredness, sleep, or recovery.
    - If they mention "since [date]", set start_date to that date and end_date to today.
    - If they mention "past two weeks", set start_date to 14 days ago.
    
    Return ONLY valid JSON.
    """
    
    try:
        response = generate_chat_response(
            messages=[{"role": "user", "content": prompt}],
            mode="normal",
            provider="xai", # Use xai/grok-fast for speed
            stream=False
        )
        
        # Parse JSON from response
        clean_response = re.sub(r'```json\s*', '', response)
        clean_response = re.sub(r'\s*```', '', clean_response)
        data = json.loads(clean_response)
        
        intent_type = IntentType(data.get("intent", "none"))
        
        return DetectedIntent(
            intent_type=intent_type,
            confidence=float(data.get("confidence", 0.0)),
            matched_keywords=[],
            activity_type_hint=data.get("activity_type"),
            time_reference=data.get("time_reference"),
            start_date=data.get("start_date"),
            end_date=data.get("end_date"),
            metrics=data.get("metrics", []),
            is_comparison=bool(data.get("is_comparison", False)),
            comparison_period=data.get("comparison_period"),
            is_chart_request=bool(data.get("is_chart_request", False) or data.get("intent") == "chart_request"),
            original_message=message
        )
        
    except Exception as e:
        logger.warning(f"LLM intent detection failed: {e}. Falling back to keyword search.")
        return detect_intent(message)


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
        "from a run", "from my run", "during my run", "during the run",
        "my run", "my workout" # Ambiguous, but usually implies specific if singular
    ]
    
    if any(k in msg_lower for k in activity_indicators):
        return "activity"
        
    # Check for specific date mention which implies activity
    if extract_specific_date(message):
        return "activity"
    
    return "trend"
