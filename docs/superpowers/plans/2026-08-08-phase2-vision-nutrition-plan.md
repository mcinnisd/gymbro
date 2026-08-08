# Phase 2: Multimodal Vision Nutrition Service Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement photo-based meal analysis using a Multimodal Vision LLM service (`app/nutrition/vision_service.py`), expose `POST /nutrition/analyze-photo` in Flask, and integrate an interactive meal review modal in the Expo mobile app.

**Architecture:** Create an isolated vision analysis service using Gemini/OpenAI vision models with fallback mock parsing for offline development. Expose a REST API endpoint that returns structured macro/calorie JSON, and connect it to `expo-image-picker` on the frontend.

**Tech Stack:** Python 3.12, Flask, Gemini Vision API / OpenAI GPT-4o, React Native Expo (`expo-image-picker`), Pytest.

## Global Constraints

- **Python Version**: Python 3.10+
- **Offline / Mock Resilience**: If vision API keys are missing or offline, the service must return structured fallback estimations without crashing.
- **Test Command**: `PYTHONPATH=. ./venv/bin/python -m pytest tests/unit/ -v`

---

### Task 1: Vision LLM Nutrition Parsing Service

**Files:**
- Create: `app/nutrition/vision_service.py`
- Test: `tests/unit/test_vision_service.py`

**Interfaces:**
- Consumes: Raw image bytes or base64 string, `LLM_PROVIDER` / `GEMINI_API_KEY` from Config.
- Produces: `analyze_meal_image(image_bytes: bytes) -> dict` returning estimated calories, protein_g, carbs_g, fat_g, quality_score, coach_notes, ingredients.

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_vision_service.py`:
```python
import pytest
from app.nutrition.vision_service import analyze_meal_image

def test_analyze_meal_image_mock_fallback():
    dummy_image_bytes = b"fake_jpeg_header_data_sample"
    result = analyze_meal_image(dummy_image_bytes)
    
    assert isinstance(result, dict)
    assert 'estimated_calories' in result
    assert 'protein_g' in result
    assert 'carbs_g' in result
    assert 'fat_g' in result
    assert 'quality_score' in result
    assert 1 <= result['quality_score'] <= 10
    assert 'meal_name' in result
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. ./venv/bin/python -m pytest tests/unit/test_vision_service.py -v`  
Expected: FAIL with `ModuleNotFoundError: No module named 'app.nutrition.vision_service'`

- [ ] **Step 3: Write minimal implementation**

Create `app/nutrition/vision_service.py`:
```python
import json
import logging
from app.config import Config

logger = logging.getLogger(__name__)

def analyze_meal_image(image_bytes: bytes) -> dict:
    # Check if Gemini/OpenAI key is available
    gemini_key = Config.GEMINI_API_KEY
    openai_key = Config.OPENAI_API_KEY
    
    if Config.LLM_PROVIDER == 'gemini' and gemini_key:
        try:
            import google.generativeai as genai
            genai.configure(api_key=gemini_key)
            model = genai.GenerativeModel('gemini-1.5-flash')
            
            prompt = """Analyze this meal image and return a JSON object with:
            {
              "meal_name": "Name of meal",
              "estimated_calories": 550,
              "protein_g": 35,
              "carbs_g": 45,
              "fat_g": 18,
              "quality_score": 8,
              "coach_notes": "Short nutrition feedback",
              "identified_ingredients": ["ingredient1", "ingredient2"]
            }
            Return ONLY raw JSON."""
            
            response = model.generate_content([
                prompt,
                {'mime_type': 'image/jpeg', 'data': image_bytes}
            ])
            text = response.text.strip().removeprefix('```json').removesuffix('```').strip()
            return json.loads(text)
        except Exception as e:
            logger.warning(f"Vision API call failed, using fallback: {e}")
            
    # Mock / Fallback estimation for offline/testing mode
    return {
        "meal_name": "Logged Meal (AI Estimated)",
        "estimated_calories": 520,
        "protein_g": 38.0,
        "carbs_g": 45.0,
        "fat_g": 18.0,
        "quality_score": 8,
        "coach_notes": "Balanced meal with solid protein and complex carbs.",
        "identified_ingredients": ["protein source", "greens", "grain base"]
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=. ./venv/bin/python -m pytest tests/unit/test_vision_service.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/nutrition/vision_service.py tests/unit/test_vision_service.py
git commit -m "feat(nutrition): implement multimodal vision meal parsing service with fallback support"
```

---

### Task 2: Flask Endpoint `POST /nutrition/analyze-photo`

**Files:**
- Modify: `app/nutrition/routes.py`
- Test: `tests/unit/test_nutrition_routes.py`

**Interfaces:**
- Consumes: Multipart form upload with field `image` or JSON with `image_base64`.
- Produces: JSON HTTP response containing estimated meal breakdown and HTTP 200 OK.

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_nutrition_routes.py`:
```python
import io
import pytest
from app import create_app

@pytest.fixture
def client():
    app = create_app()
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_analyze_photo_endpoint(client):
    data = {
        'image': (io.BytesIO(b"fake_image_bytes"), 'test_meal.jpg')
    }
    response = client.post('/nutrition/analyze-photo', data=data, content_type='multipart/form-data')
    assert response.status_code == 200
    json_data = response.get_json()
    assert 'estimated_calories' in json_data
    assert 'meal_name' in json_data
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. ./venv/bin/python -m pytest tests/unit/test_nutrition_routes.py -v`  
Expected: FAIL with HTTP 404 (Endpoint Not Found).

- [ ] **Step 3: Write minimal implementation**

Update `app/nutrition/routes.py`:
Add route handler `/analyze-photo`:
```python
from flask import request, jsonify
from . import nutrition_bp
from .vision_service import analyze_meal_image

@nutrition_bp.route('/analyze-photo', methods=['POST'])
def analyze_photo():
    image_bytes = None
    if 'image' in request.files:
        image_bytes = request.files['image'].read()
    elif request.is_json and 'image_base64' in request.json:
        import base64
        image_bytes = base64.b64decode(request.json['image_base64'])
        
    if not image_bytes:
        return jsonify({'error': 'No image provided'}), 400
        
    analysis = analyze_meal_image(image_bytes)
    return jsonify(analysis), 200
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=. ./venv/bin/python -m pytest tests/unit/test_nutrition_routes.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/nutrition/routes.py tests/unit/test_nutrition_routes.py
git commit -m "feat(nutrition): add POST /nutrition/analyze-photo REST API endpoint"
```

---

### Task 3: Expo Mobile App Photo Upload & Confirmation Sheet Integration

**Files:**
- Modify: `gymbro-frontend-expo/app/(tabs)/nutrition.tsx`

**Interfaces:**
- Consumes: `POST /nutrition/analyze-photo` and `POST /nutrition/log`.
- Produces: Camera/Photo-picker modal button, interactive bottom confirmation sheet allowing user to edit macro numbers before saving meal.

- [ ] **Step 1: Add photo pick action and analysis state to `nutrition.tsx`**

Add image picker state (`selectedImage`, `isAnalyzing`, `analysisResult`, `showModal`) and handle photo pick via `expo-image-picker`.

- [ ] **Step 2: Run frontend typecheck**

Run: `cd gymbro-frontend-expo && npx tsc --noEmit`  
Expected: PASS with 0 errors.

- [ ] **Step 3: Commit**

```bash
git add gymbro-frontend-expo/app/\(tabs\)/nutrition.tsx
git commit -m "feat(expo): integrate photo meal scanning and interactive macro confirmation modal"
```
