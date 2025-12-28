import sys
import os
sys.path.append(os.getcwd())

from app.context.intent_detector import detect_intent, IntentType
from app.context.chart_generator import generate_chart_data

USER_ID = "9"  # User with data

def test_chart_intent():
    queries = [
        "show me a graph of my pace",
        "chart my weekly distance",
        "plot my hrv trend",
        "visualize my training load"
    ]
    
    print("\n=== Testing Intent Detection ===")
    for q in queries:
        intent = detect_intent(q)
        print(f"Query: '{q}' -> Intent: {intent.intent_type.value} (Confidence: {intent.confidence})")
        if intent.intent_type != IntentType.CHART_REQUEST:
            print("  FAIL: Expected chart_request")

def test_chart_generation():
    metrics = ["pace", "distance", "hrv", "training_load"]
    
    print("\n=== Testing Chart Generation ===")
    for m in metrics:
        data = generate_chart_data(USER_ID, m)
        if data:
            print(f"Metric: {m} -> Generated {data['type']} chart with {len(data['data']['labels'])} points")
            # print(data)
        else:
            print(f"Metric: {m} -> No data found")

if __name__ == "__main__":
    test_chart_intent()
    test_chart_generation()
