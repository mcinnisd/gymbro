"""
Multi-Hop RAG Engine for GYMBro Context Building.

Aggregates relational health metrics (sleep, HRV, resting HR),
recent activities (running, workouts), daily journal entries, and vector-searched
user intelligence notes into a cohesive context payload.
"""

from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import logging

from app.supabase_client import supabase
from app.context.intelligence_service import IntelligenceService
from app.context.baseline_service import get_user_baselines

logger = logging.getLogger(__name__)


def retrieve_vector_notes(user_id: str, query: str, limit: int = 5) -> List[Dict[str, Any]]:
    """
    Perform hybrid vector/keyword search across user intelligence, journal entries,
    and athlete memories.
    """
    notes = []

    # 1. Search user_intelligence using vector/keyword search
    try:
        intel_results = IntelligenceService.search_intelligence(user_id, query, limit=limit)
        if intel_results and isinstance(intel_results, list):
            for item in intel_results:
                notes.append({
                    "source": "intelligence",
                    "category": item.get("category", "fact"),
                    "content": item.get("content", ""),
                    "created_at": item.get("created_at")
                })
    except Exception as e:
        logger.warning(f"Error fetching intelligence vector notes: {e}")

    # 2. Query daily_journals table for entries
    if supabase:
        try:
            uid = int(user_id) if str(user_id).isdigit() else user_id
            res = supabase.table("daily_journals")\
                .select("*")\
                .eq("user_id", uid)\
                .order("date", desc=True)\
                .limit(limit)\
                .execute()
            if res and hasattr(res, "data") and res.data:
                for j in res.data:
                    ans = j.get("answers") or {}
                    text = ans.get("journal_text") or j.get("journal_text") or ""
                    notes.append({
                        "source": "daily_journal",
                        "date": j.get("date"),
                        "energy_level": ans.get("energy_level") or j.get("energy_level"),
                        "felt_sore": ans.get("felt_sore") or j.get("felt_sore"),
                        "content": f"Journal ({j.get('date')}): Energy={ans.get('energy_level', 'N/A')}/10, Sore={ans.get('felt_sore', False)}. Notes: {text}"
                    })
        except Exception as e:
            logger.warning(f"Error fetching daily journals for RAG: {e}")

        # 3. Query athlete_memories table
        try:
            uid = int(user_id) if str(user_id).isdigit() else user_id
            mem_res = supabase.table("athlete_memories")\
                .select("*")\
                .eq("user_id", uid)\
                .limit(limit)\
                .execute()
            if mem_res and hasattr(mem_res, "data") and mem_res.data:
                for m in mem_res.data:
                    notes.append({
                        "source": "athlete_memory",
                        "category": m.get("category", "memory"),
                        "content": m.get("content_text", "")
                    })
        except Exception as e:
            logger.warning(f"Error fetching athlete memories: {e}")

    return notes


def retrieve_relational_metrics(user_id: str, days: int = 30, date_bounds: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Fetch relational health & activity metrics (sleep, HRV, RHR, activities, biometrics).
    """
    cutoff = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
    start_date = date_bounds.get("start_date") if date_bounds and "start_date" in date_bounds else cutoff
    end_date = date_bounds.get("end_date") if date_bounds and "end_date" in date_bounds else datetime.now().strftime('%Y-%m-%d')

    uid = int(user_id) if str(user_id).isdigit() else user_id
    metrics = {
        "sleep": [],
        "hrv": [],
        "rhr": [],
        "activities": [],
        "baselines": {}
    }

    if not supabase:
        return metrics

    # 1. Garmin sleep & HRV
    try:
        sleep_res = supabase.table("garmin_sleep")\
            .select("*")\
            .eq("user_id", uid)\
            .gte("date", start_date)\
            .lte("date", end_date)\
            .execute()
        if sleep_res and hasattr(sleep_res, "data") and sleep_res.data:
            for s in sleep_res.data:
                sd = s.get("sleep_data") or {}
                hours = sd.get("sleepTimeSeconds", 0) / 3600 if sd.get("sleepTimeSeconds") else s.get("sleep_hours", 0)
                hrv = sd.get("avgOvernightHrv") or s.get("hrv")
                metrics["sleep"].append({
                    "date": s.get("date"),
                    "sleep_hours": round(hours, 1) if hours else None,
                    "sleep_score": sd.get("sleepScores", {}).get("overall", {}).get("value") or s.get("sleep_score"),
                    "hrv": hrv
                })
                if hrv:
                    metrics["hrv"].append({"date": s.get("date"), "hrv": hrv})
    except Exception as e:
        logger.warning(f"Error fetching garmin_sleep in RAG: {e}")

    # 2. Daily biometrics (garmin_daily or biometrics_daily)
    try:
        daily_res = supabase.table("garmin_daily")\
            .select("*")\
            .eq("user_id", uid)\
            .gte("date", start_date)\
            .lte("date", end_date)\
            .execute()
        if daily_res and hasattr(daily_res, "data") and daily_res.data:
            for d in daily_res.data:
                rhr = d.get("resting_hr")
                if isinstance(rhr, dict):
                    rhr = rhr.get("restingHeartRate") or rhr.get("value")
                if rhr:
                    metrics["rhr"].append({"date": d.get("date"), "resting_hr": rhr})
    except Exception as e:
        logger.warning(f"Error fetching garmin_daily in RAG: {e}")

    try:
        bio_res = supabase.table("biometrics_daily")\
            .select("*")\
            .eq("user_id", uid)\
            .gte("date", start_date)\
            .lte("date", end_date)\
            .execute()
        if bio_res and hasattr(bio_res, "data") and bio_res.data:
            for b in bio_res.data:
                if b.get("sleep_hours"):
                    metrics["sleep"].append({
                        "date": b.get("date"),
                        "sleep_hours": b.get("sleep_hours"),
                        "hrv": b.get("hrv")
                    })
                if b.get("hrv"):
                    metrics["hrv"].append({"date": b.get("date"), "hrv": b.get("hrv")})
                if b.get("resting_hr"):
                    metrics["rhr"].append({"date": b.get("date"), "resting_hr": b.get("resting_hr")})
    except Exception as e:
        logger.warning(f"Error fetching biometrics_daily in RAG: {e}")

    # 3. Activities (garmin_activities & activities)
    try:
        act_res = supabase.table("garmin_activities")\
            .select("*")\
            .eq("user_id", uid)\
            .gte("start_time_local", start_date)\
            .execute()
        if act_res and hasattr(act_res, "data") and act_res.data:
            for a in act_res.data:
                raw = a.get("raw_data") or {}
                dist_km = (a.get("distance") or 0) / 1000 if (a.get("distance") or 0) > 100 else (a.get("distance") or 0)
                dur_min = (a.get("duration") or 0) / 60 if (a.get("duration") or 0) > 300 else (a.get("duration") or 0)
                avg_hr = a.get("average_hr") or raw.get("averageHR")
                metrics["activities"].append({
                    "name": a.get("activity_name", "Workout"),
                    "type": a.get("activity_type", "running"),
                    "date": str(a.get("start_time_local", ""))[:10],
                    "distance_km": round(dist_km, 2),
                    "duration_min": round(dur_min, 1),
                    "avg_hr": avg_hr,
                    "calories": a.get("calories")
                })
    except Exception as e:
        logger.warning(f"Error fetching garmin_activities in RAG: {e}")

    try:
        gen_act_res = supabase.table("activities")\
            .select("*")\
            .eq("user_id", uid)\
            .execute()
        if gen_act_res and hasattr(gen_act_res, "data") and gen_act_res.data:
            for a in gen_act_res.data:
                dist_km = (a.get("distance") or 0) / 1000 if (a.get("distance") or 0) > 100 else (a.get("distance") or 0)
                dur_min = (a.get("duration") or 0) / 60 if (a.get("duration") or 0) > 300 else (a.get("duration") or 0)
                metrics["activities"].append({
                    "name": a.get("activity_name") or a.get("name", "Activity"),
                    "type": a.get("activity_type") or a.get("type", "workout"),
                    "date": str(a.get("start_time_local") or a.get("created_at", ""))[:10],
                    "distance_km": round(dist_km, 2),
                    "duration_min": round(dur_min, 1),
                    "avg_hr": a.get("average_hr"),
                    "calories": a.get("calories")
                })
    except Exception as e:
        logger.warning(f"Error fetching activities in RAG: {e}")

    # 4. Baselines
    try:
        metrics["baselines"] = get_user_baselines(user_id)
    except Exception as e:
        logger.warning(f"Error getting baselines in RAG: {e}")

    return metrics


def build_multihop_rag_bundle(user_id: str, query: str, date_bounds: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Multi-hop RAG context aggregation engine.
    Combines relational health metrics (sleep, HRV, activities) along with vector search notes and journal entries.
    """
    notes = retrieve_vector_notes(user_id, query, limit=5)
    relational = retrieve_relational_metrics(user_id, days=30, date_bounds=date_bounds)

    return {
        "user_id": user_id,
        "query": query,
        "notes": notes,
        "relational_metrics": relational,
        "timestamp": datetime.now().isoformat()
    }
