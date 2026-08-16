# app/coach/prepopulate_service.py
"""
Coach Pre-Population Service Adapter.
Delegates to the canonical TelemetryPrepopulateService in app.onboarding.
"""

import logging
from typing import Dict, Any, Optional
from app.onboarding.prepopulate_service import TelemetryPrepopulateService, format_duration

logger = logging.getLogger(__name__)


def calculate_prepopulation_data(user_id: Any) -> Optional[Dict[str, Any]]:
    """
    Scrapes Garmin, Strava & Apple Health data from Supabase, estimates demographic and performance metrics,
    and returns a pre-populated profile dictionary for verification.
    """
    try:
        return TelemetryPrepopulateService.get_prepopulation_data(user_id)
    except Exception as e:
        logger.error(f"Error calculating prepopulate data: {e}")
        return None
