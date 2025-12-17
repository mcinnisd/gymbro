"""
Proactive Coaching Module (Phase 4)

Generates intelligent coaching suggestions based on user patterns:
- Training consistency analysis
- Recovery recommendations
- Performance optimization tips
- Goal progress tracking
"""

from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from app.supabase_client import supabase


def generate_proactive_insights(user_id: str, baselines: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Generate proactive coaching insights based on user's patterns.
    
    Returns a list of suggestions with:
    - type: 'warning', 'tip', 'celebration', 'goal'
    - priority: 1-5 (1 = highest)
    - title: Short title
    - message: Detailed message
    - action: Suggested action (optional)
    """
    insights = []
    
    running = baselines.get("running", {})
    health = baselines.get("health", {})
    training_load = baselines.get("training_load", {})
    
    # === TRAINING CONSISTENCY ===
    if running.get("has_data"):
        runs_per_week = running.get("runs_per_week", 0)
        
        # Low frequency warning
        if runs_per_week < 2:
            insights.append({
                "type": "tip",
                "priority": 2,
                "title": "Boost Your Consistency",
                "message": f"You're averaging {runs_per_week} runs per week. For aerobic development, aim for 3-4 runs weekly. Even short easy runs count!",
                "action": "Schedule 2-3 short recovery runs this week"
            })
        
        # Great consistency celebration
        elif runs_per_week >= 4:
            insights.append({
                "type": "celebration",
                "priority": 4,
                "title": "Great Consistency! 🎉",
                "message": f"You're averaging {runs_per_week} runs per week - excellent training frequency!",
                "action": None
            })
    
    # === TRAINING LOAD ANALYSIS ===
    if training_load.get("last_7_days") and training_load.get("previous_7_days"):
        current = training_load["last_7_days"]
        previous = training_load["previous_7_days"]
        change = training_load.get("change", {})
        
        dist_change = change.get("distance_pct", 0)
        
        # Sudden volume increase warning
        if dist_change > 25:
            insights.append({
                "type": "warning",
                "priority": 1,
                "title": "Volume Spike Detected",
                "message": f"Your training volume increased {dist_change:.0f}% vs last week. Rapid increases can lead to injury. Consider a recovery day.",
                "action": "Add an extra rest or easy day this week"
            })
        
        # Volume drop - might be tapering or losing motivation
        elif dist_change < -30:
            insights.append({
                "type": "tip",
                "priority": 3,
                "title": "Training Volume Down",
                "message": f"You ran {abs(dist_change):.0f}% less than last week. If intentional (taper/recovery), great! If not, let's get back on track.",
                "action": "Plan your next run for tomorrow"
            })
    
    # === RECOVERY INSIGHTS ===
    if health.get("avg_hrv") and health.get("avg_rhr"):
        avg_hrv = health["avg_hrv"]
        avg_rhr = health["avg_rhr"]
        avg_sleep = health.get("avg_sleep_hours", 0)
        
        # Poor sleep affecting recovery
        if avg_sleep and avg_sleep < 6.5:
            insights.append({
                "type": "warning",
                "priority": 1,
                "title": "Sleep Debt Alert",
                "message": f"You're averaging only {avg_sleep:.1f} hours of sleep. This impacts recovery and performance. Aim for 7-8 hours.",
                "action": "Set a consistent bedtime 30 min earlier"
            })
        
        # High RHR suggests need for recovery
        if avg_rhr > 60:  # Rough threshold - should be personalized
            insights.append({
                "type": "tip",
                "priority": 3,
                "title": "Recovery Focus",
                "message": f"Your resting heart rate is elevated at {avg_rhr:.0f} bpm. Consider lighter training until it normalizes.",
                "action": "Replace one hard workout with easy running"
            })
    
    # === PERFORMANCE OPTIMIZATION ===
    if running.get("has_data") and running.get("avg_hr"):
        avg_hr = running["avg_hr"]
        avg_pace = running.get("avg_pace_sec_km", 0)
        
        # High HR relative to pace - aerobic base needed
        if avg_hr and avg_hr > 160:
            insights.append({
                "type": "tip",
                "priority": 2,
                "title": "Build Your Aerobic Base",
                "message": f"Your average running HR is {avg_hr:.0f} bpm - on the higher side. Adding more easy Zone 2 runs can improve efficiency.",
                "action": "Include 2-3 runs at conversational pace (Zone 2)"
            })
    
    # === GOAL PROGRESS ===
    # TODO: Check user's goals and provide progress updates
    
    # Sort by priority
    insights.sort(key=lambda x: x["priority"])
    
    return insights


def get_proactive_context(user_id: str, baselines: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get proactive coaching context for injection into chat.
    """
    insights = generate_proactive_insights(user_id, baselines)
    
    if not insights:
        return {}
    
    return {
        "insights": insights,
        "top_priority": insights[0] if insights else None,
        "total_count": len(insights)
    }


def format_proactive_context(context: Dict[str, Any]) -> str:
    """
    Format proactive insights for prompt injection.
    """
    if not context or not context.get("insights"):
        return ""
    
    lines = ["\n🎯 PROACTIVE COACHING INSIGHTS:"]
    
    for insight in context.get("insights", [])[:3]:  # Top 3 only
        icon = {
            "warning": "⚠️",
            "tip": "💡",
            "celebration": "🎉",
            "goal": "🎯"
        }.get(insight["type"], "📌")
        
        lines.append(f"\n{icon} {insight['title']}")
        lines.append(f"   {insight['message']}")
        if insight.get("action"):
            lines.append(f"   → Suggestion: {insight['action']}")
    
    return "\n".join(lines)
