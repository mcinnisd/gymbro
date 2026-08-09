"""
Context Builder Module for Multi-Hop RAG & AI Coach Context Generation.
"""

from typing import Dict, Any, Optional
from app.memory.rag import build_multihop_rag_bundle, retrieve_vector_notes, retrieve_relational_metrics


def build_user_context(user_id: str, query: str, date_bounds: Optional[Dict[str, Any]] = None) -> str:
    """
    Build user context by aggregating relational health metrics (sleep, HRV, activities)
    along with vector search notes and journal entries.

    Args:
        user_id: User identifier
        query: User message/question string
        date_bounds: Optional dictionary with historical date bounds (start_date, end_date)

    Returns:
        Formatted context string containing sleep, HRV, activities, notes, and journal entries.
    """
    bundle = build_multihop_rag_bundle(user_id, query, date_bounds=date_bounds)
    relational = bundle.get("relational_metrics", {})
    notes = bundle.get("notes", [])

    context_lines = []
    context_lines.append(f"=== Multi-Hop Context for Query: '{query}' ===")

    # 1. Health & Sleep Metrics (Relational)
    context_lines.append("\n### Sleep & HRV Metrics:")
    sleep_data = relational.get("sleep", [])
    hrv_data = relational.get("hrv", [])
    rhr_data = relational.get("rhr", [])

    if sleep_data:
        for s in sleep_data:
            sh = f"{s['sleep_hours']}h" if s.get("sleep_hours") is not None else "N/A"
            sc = f"Score: {s['sleep_score']}" if s.get("sleep_score") is not None else ""
            hrv_str = f"HRV: {s['hrv']}ms" if s.get("hrv") is not None else ""
            context_lines.append(f"- Date {s.get('date')}: Sleep duration {sh} {sc} {hrv_str}".strip())
    else:
        context_lines.append("- Sleep: No recent Garmin sleep records found.")

    if hrv_data and not sleep_data:
        for h in hrv_data:
            context_lines.append(f"- Date {h.get('date')}: HRV = {h.get('hrv')} ms")

    if rhr_data:
        rhr_vals = [str(r.get("resting_hr")) for r in rhr_data if r.get("resting_hr")]
        if rhr_vals:
            context_lines.append(f"- Resting Heart Rate (RHR) samples: {', '.join(rhr_vals)} bpm")

    # 2. Activities (Relational)
    context_lines.append("\n### Recent Activities:")
    activities = relational.get("activities", [])
    if activities:
        for act in activities:
            dist = f"{act['distance_km']} km" if act.get("distance_km") else ""
            dur = f"{act['duration_min']} min" if act.get("duration_min") else ""
            hr = f"Avg HR: {act['avg_hr']} bpm" if act.get("avg_hr") else ""
            context_lines.append(f"- [{act.get('date')}] {act.get('name')} ({act.get('type')}): {dist} {dur} {hr}".strip())
    else:
        context_lines.append("- Activities: No recent workout logs recorded.")

    # 3. Baselines summary
    baselines = relational.get("baselines", {})
    if baselines:
        health_base = baselines.get("health", {})
        run_base = baselines.get("running", {})
        if health_base.get("has_data") or run_base.get("has_data"):
            context_lines.append("\n### Health & Running Baselines:")
            if health_base.get("has_data"):
                context_lines.append(f"- Health norm: Sleep avg = {health_base.get('avg_sleep_hours', 'N/A')}h, HRV avg = {health_base.get('avg_hrv', 'N/A')}ms")
            if run_base.get("has_data"):
                context_lines.append(f"- Running norm: Avg distance = {run_base.get('total_distance_km', 'N/A')}km, Avg pace = {run_base.get('avg_pace_sec_km', 'N/A')}s/km")

    # 4. Vector Search Notes & Journal Entries
    context_lines.append("\n### Relevant Notes & Journal Entries:")
    if notes:
        for n in notes:
            src = n.get("source", "note")
            content = n.get("content", "")
            date_str = f" ({n['date']})" if n.get("date") else ""
            context_lines.append(f"- [{src.upper()}{date_str}] {content}")
    else:
        context_lines.append("- Notes & Journal: No matching vector notes or journal entries found.")

    return "\n".join(context_lines)
