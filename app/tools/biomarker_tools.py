"""
Biomarker & Bloodwork Query Tools for LLM Function Calling.
Exposes tools for the AI Coach to retrieve athlete bloodwork, flagged analytes,
and longitudinal biomarker trend charts with gymbro.widget/v1 payloads.
"""

import logging
from typing import Dict, Any, List, Optional
from app.biomarkers.service import (
    get_flagged_biomarkers,
    get_biomarker_trends,
    get_biomarker_summary,
    get_user_panels,
    get_panel_details
)
from app.agent.widget_protocol import build_interactive_chart_widget

logger = logging.getLogger(__name__)


def get_biomarkers(
    user_id: str,
    marker_name: Optional[str] = None,
    category: Optional[str] = None,
    flagged_only: bool = False
) -> Dict[str, Any]:
    """
    Retrieves lab bloodwork biomarkers for an athlete.

    Args:
        user_id: The ID of the user.
        marker_name: Optional specific biomarker name (e.g. 'Ferritin', 'hs-CRP', 'Vitamin D').
        category: Optional category filter (e.g. 'Iron & Oxygen', 'Inflammation & Recovery', 'Cardiometabolic & Lipids').
        flagged_only: If True, returns only out-of-range flagged analytes.

    Returns:
        Dict containing status, panel information, summary counts, and list of biomarkers.
    """
    try:
        uid = int(user_id) if str(user_id).isdigit() else user_id

        if flagged_only:
            flagged = get_flagged_biomarkers(uid)
            if marker_name:
                flagged = [f for f in flagged if marker_name.lower() in f.get('marker_name', '').lower()]
            if category:
                flagged = [f for f in flagged if category.lower() in (f.get('category') or '').lower()]

            return {
                "status": "success",
                "count": len(flagged),
                "flagged_only": True,
                "biomarkers": flagged
            }

        panels = get_user_panels(uid)
        if not panels:
            return {
                "status": "success",
                "count": 0,
                "message": "No bloodwork lab panels on file for this athlete.",
                "biomarkers": []
            }

        latest_panel = panels[0]
        panel_details = get_panel_details(uid, latest_panel.get('id'))
        markers = panel_details.get('biomarkers', []) if panel_details else []

        if marker_name:
            markers = [m for m in markers if marker_name.lower() in m.get('marker_name', '').lower()]
        if category:
            markers = [m for m in markers if category.lower() in (m.get('category') or '').lower()]

        return {
            "status": "success",
            "panel_id": latest_panel.get('id'),
            "test_date": latest_panel.get('test_date'),
            "provider_name": latest_panel.get('provider_name'),
            "count": len(markers),
            "biomarkers": markers
        }
    except Exception as e:
        logger.error(f"Error in get_biomarkers tool for user {user_id}: {e}")
        return {"status": "error", "message": str(e), "biomarkers": []}


def get_biomarker_trends_tool(
    user_id: str,
    marker_name: Optional[str] = None,
    category: Optional[str] = None
) -> Dict[str, Any]:
    """
    Retrieves longitudinal biomarker trends across all historical lab panels,
    including delta progression, % change, trajectory direction, and interactive chart widget.

    Args:
        user_id: The ID of the user.
        marker_name: Optional specific analyte name (e.g. 'Ferritin').
        category: Optional category filter.

    Returns:
        Dict containing trends list and embedded gymbro.widget/v1 interactive chart payload.
    """
    try:
        uid = int(user_id) if str(user_id).isdigit() else user_id
        marker_names = [marker_name] if marker_name else None
        trends = get_biomarker_trends(uid, marker_names=marker_names, category=category)

        if not trends:
            return {
                "status": "success",
                "count": 0,
                "message": "No historical longitudinal bloodwork trends found.",
                "trends": []
            }

        # Build interactive chart widget for the primary trend
        primary_trend = trends[0]
        points = []
        for pt in primary_trend.get('data_points', []):
            points.append({
                "timestamp": f"{pt['date']}T08:00:00Z",
                "value": pt['value'],
                "status": pt.get('status', 'optimal'),
                "ref_min": pt.get('ref_min'),
                "ref_max": pt.get('ref_max')
            })

        metrics = [
            {
                "key": primary_trend['marker_name'].lower().replace(' ', '_'),
                "label": primary_trend['marker_name'],
                "unit": primary_trend['unit'],
                "color": "#E07A5F" if primary_trend['latest_status'] != 'optimal' else "#2D6A4F",
                "corridor_min": primary_trend.get('ref_range_min'),
                "corridor_max": primary_trend.get('ref_range_max')
            }
        ]

        widget = build_interactive_chart_widget(
            title=f"{primary_trend['marker_name']} Longitudinal Trend",
            subtitle=f"{primary_trend['category']} ({primary_trend['unit']})",
            time_range="All-Time Lab History",
            metrics=metrics,
            points=points,
            summary_insight=primary_trend.get('insight')
        )

        return {
            "status": "success",
            "count": len(trends),
            "trends": trends,
            "widget": widget
        }
    except Exception as e:
        logger.error(f"Error in get_biomarker_trends_tool for user {user_id}: {e}")
        return {"status": "error", "message": str(e), "trends": []}
