# Context Intelligence Module
# Provides contextual awareness for coach chat

from .intent_detector import detect_intent, IntentType
from .context_builder import build_context
from .baseline_service import get_user_baselines

__all__ = ['detect_intent', 'IntentType', 'build_context', 'get_user_baselines']
