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
    user_ids = [str(user_id)]
    if str(user_id).isdigit():
        user_ids.append(int(user_id))

    # 1. Search user_intelligence using vector/keyword search
    try:
        intel_results = IntelligenceService.search_intelligence(str(user_id), query, limit=limit)
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
        for uid in user_ids:
            try:
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
                    break
            except Exception as e:
                logger.warning(f"Error fetching daily journals for RAG: {e}")

    return notes


def retrieve_relational_metrics(user_id: str, days: int = 60, date_bounds: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Fetch relational health & activity metrics (sleep, HRV, RHR, activities, biometrics).
    Robustly queries both string and integer user_id representations.
    """
    user_ids = [str(user_id)]
    if str(user_id).isdigit():
        user_ids.append(int(user_id))

    metrics = {
        "sleep": [],
        "hrv": [],
        "rhr": [],
        "activities": [],
        "baselines": {}
    }

    if not supabase:
        return metrics

    # 1. Biometrics daily & Garmin sleep
    for uid in user_ids:
        try:
            bio_res = supabase.table("biometrics_daily")\
                .select("*")\
                .eq("user_id", uid)\
                .order("date", desc=True)\
                .limit(30)\
                .execute()
            if bio_res and hasattr(bio_res, "data") and bio_res.data:
                for b in bio_res.data:
                    dur_s = b.get("sleep_duration_seconds")
                    hours = (dur_s / 3600) if dur_s else b.get("sleep_hours")
                    hrv = b.get("hrv_avg") or b.get("hrv")
                    score = b.get("sleep_score")
                    rhr = b.get("resting_hr")
                    if hours or score or hrv:
                        metrics["sleep"].append({
                            "date": b.get("date"),
                            "sleep_hours": round(float(hours), 1) if hours else None,
                            "sleep_score": int(score) if score else None,
                            "hrv": float(hrv) if hrv else None
                        })
                    if hrv:
                        metrics["hrv"].append({"date": b.get("date"), "hrv": float(hrv)})
                    if rhr:
                        metrics["rhr"].append({"date": b.get("date"), "resting_hr": float(rhr)})
                break
        except Exception as e:
            logger.warning(f"Error fetching biometrics_daily in RAG: {e}")

    # Fallback to garmin_sleep if sleep metrics are still empty
    if not metrics["sleep"]:
        for uid in user_ids:
            try:
                sleep_res = supabase.table("garmin_sleep")\
                    .select("*")\
                    .eq("user_id", uid)\
                    .order("date", desc=True)\
                    .limit(30)\
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
                    break
            except Exception as e:
                logger.warning(f"Error fetching garmin_sleep in RAG: {e}")


    # 2. Daily biometrics
    for uid in user_ids:
        try:
            daily_res = supabase.table("garmin_daily")\
                .select("*")\
                .eq("user_id", uid)\
                .order("date", desc=True)\
                .limit(30)\
                .execute()
            if daily_res and hasattr(daily_res, "data") and daily_res.data:
                for d in daily_res.data:
                    rhr = d.get("resting_hr")
                    if isinstance(rhr, dict):
                        rhr = rhr.get("restingHeartRate") or rhr.get("value")
                    if rhr:
                        metrics["rhr"].append({"date": d.get("date"), "resting_hr": rhr})
                break
        except Exception as e:
            logger.warning(f"Error fetching garmin_daily in RAG: {e}")

    # 3. Garmin activities & Strava workouts
    for uid in user_ids:
        try:
            act_res = supabase.table("garmin_activities")\
                .select("*")\
                .eq("user_id", uid)\
                .order("synced_at", desc=True)\
                .limit(50)\
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
                break
        except Exception as e:
            logger.warning(f"Error fetching garmin_activities in RAG: {e}")

    for uid in user_ids:
        try:
            strava_res = supabase.table("strava_activities")\
                .select("*")\
                .eq("user_id", uid)\
                .order("start_date", desc=True)\
                .limit(50)\
                .execute()
            if strava_res and hasattr(strava_res, "data") and strava_res.data:
                for a in strava_res.data:
                    dist_km = (a.get("distance") or 0) / 1000 if (a.get("distance") or 0) > 100 else (a.get("distance") or 0)
                    dur_min = (a.get("moving_time") or a.get("elapsed_time") or 0) / 60
                    metrics["activities"].append({
                        "name": a.get("name", "Strava Activity"),
                        "type": a.get("type", "workout"),
                        "date": str(a.get("start_date", ""))[:10],
                        "distance_km": round(dist_km, 2),
                        "duration_min": round(dur_min, 1),
                        "avg_hr": a.get("average_heartrate"),
                        "calories": a.get("calories")
                    })
                break
        except Exception:
            pass

    # 4. Baselines
    try:
        metrics["baselines"] = get_user_baselines(str(user_id))
    except Exception as e:
        logger.warning(f"Error getting baselines in RAG: {e}")

    return metrics


def build_multihop_rag_bundle(user_id: str, query: str, date_bounds: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Multi-hop RAG context aggregation engine.
    Combines relational health metrics (sleep, HRV, activities) along with vector search notes and journal entries.
    """
    notes = retrieve_vector_notes(user_id, query, limit=5)
    relational = retrieve_relational_metrics(user_id, days=60, date_bounds=date_bounds)

    return {
        "user_id": user_id,
        "query": query,
        "notes": notes,
        "relational_metrics": relational,
        "timestamp": datetime.now().isoformat()
    }
