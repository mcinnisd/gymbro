import os
import base64
import json
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
from flask import Flask, request, jsonify
from pymongo import MongoClient
from openai import OpenAI  # Ensure you have the OpenAI Python package installed
from werkzeug.security import generate_password_hash, check_password_hash
import jwt
from functools import wraps

# Load environment variables
load_dotenv()

# Configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
MONGO_URI = os.getenv("MONGO_URI", "mongodb://127.0.0.1:27017/")
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your_jwt_secret_key")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
TOKEN_EXPIRATION_MINUTES = 30  # Token validity duration

# Initialize OpenAI client
openai_client = OpenAI(api_key=OPENAI_API_KEY)

# Initialize Flask app
app = Flask(__name__)

# MongoDB Setup
client = MongoClient(MONGO_URI)
db = client["gymbro_db"]
food_logs = db["food_logs"]
users = db["users"]  # New collection for users

def token_required(f):
    """
    Decorator to ensure that the request contains a valid JWT.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None

        # JWT is expected in the Authorization header as Bearer token
        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            parts = auth_header.split()
            if len(parts) == 2 and parts[0].lower() == 'bearer':
                token = parts[1]

        if not token:
            return jsonify({"error": "Token is missing!"}), 401

        try:
            data = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
            current_user = users.find_one({"_id": data['user_id']})
            if not current_user:
                return jsonify({"error": "User not found!"}), 401
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Token has expired!"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": "Invalid token!"}), 401

        # Attach current_user to the request context
        request.current_user = current_user
        return f(*args, **kwargs)
    return decorated

def encode_image(image_bytes):
    """
    Encode image bytes to a base64 string.
    """
    try:
        return base64.b64encode(image_bytes).decode("utf-8")
    except Exception as e:
        print(f"Error encoding image: {e}")
        return None

def get_openai_prediction(encoded_image):
    """
    Send the encoded image to OpenAI and get macro predictions.
    """
    prompt = (
        "You are a professional at analyzing food and predicting the total calories, fat, carbohydrates, and protein within the meal. "
        "Use your superior skills to accurately predict what is contained in the meal in the following image. "
        "Please provide your response in a structured JSON format containing only the following fields without any units: calories, fat, "
        "carbohydrates, and protein. Do not include any additional text, explanations, or formatting."
    )
    
    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",  # Ensure this is the correct model name
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{encoded_image}",
                                "detail": "low"
                            },
                        },
                    ],
                }
            ],
            max_tokens=300,
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"Error calling OpenAI API: {e}")
        return None

def clean_response(response_text):
    """
    Clean the response text to extract JSON by removing Markdown code block delimiters.
    """
    if response_text.startswith("```") and response_text.endswith("```"):
        lines = response_text.split('\n')
        if len(lines) >= 3:
            return '\n'.join(lines[1:-1])
    return response_text

def parse_openai_response(response_text):
    """
    Parse the OpenAI JSON response to extract macro estimates.
    """
    try:
        cleaned_response = clean_response(response_text)
        data = json.loads(cleaned_response)
        
        # Normalize keys
        normalized_data = {}
        for key, value in data.items():
            normalized_key = key.split('(')[0].strip().lower()
            normalized_data[normalized_key] = value
        
        # Extract required fields
        calories = normalized_data.get("calories")
        fat = normalized_data.get("fat")
        carbohydrates = normalized_data.get("carbohydrates")
        protein = normalized_data.get("protein")
        
        if None in (calories, fat, carbohydrates, protein):
            print("Missing one or more required fields in the response.")
            return None
        
        return {
            "calories": calories,
            "fat": fat,
            "carbohydrates": carbohydrates,
            "protein": protein
        }
    except json.JSONDecodeError:
        print("Failed to parse response as JSON.")
        return None
    except Exception as e:
        print(f"Error parsing OpenAI response: {e}")
        return None

@app.route("/register", methods=["POST"])
def register():
    """
    Endpoint: POST /register
    Body: JSON with 'username' and 'password'
    Returns: JSON with success message or error
    """
    data = request.get_json()
    if not data or not data.get("username") or not data.get("password"):
        return jsonify({"error": "Username and password are required."}), 400
    
    username = data["username"]
    password = data["password"]
    
    if users.find_one({"username": username}):
        return jsonify({"error": "Username already exists."}), 400
    
    hashed_password = generate_password_hash(password)
    
    user_doc = {
        "username": username,
        "password": hashed_password,
        "created_at": datetime.now(timezone.utc)
    }
    
    try:
        insert_result = users.insert_one(user_doc)
        return jsonify({"message": "User registered successfully."}), 201
    except Exception as e:
        print(f"Error registering user: {e}")
        return jsonify({"error": "Registration failed."}), 500

@app.route("/login", methods=["POST"])
def login():
    """
    Endpoint: POST /login
    Body: JSON with 'username' and 'password'
    Returns: JSON with JWT token or error
    """
    data = request.get_json()
    if not data or not data.get("username") or not data.get("password"):
        return jsonify({"error": "Username and password are required."}), 400
    
    username = data["username"]
    password = data["password"]
    
    user = users.find_one({"username": username})
    if not user or not check_password_hash(user["password"], password):
        return jsonify({"error": "Invalid username or password."}), 401
    
    token_payload = {
        "user_id": str(user["_id"]),
        "exp": datetime.utcnow() + timedelta(minutes=TOKEN_EXPIRATION_MINUTES)
    }
    
    token = jwt.encode(token_payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    
    return jsonify({"token": token}), 200

@app.route("/food_analysis", methods=["POST"])
@token_required
def analyze_food():
    """
    Endpoint: POST /food_analysis
    Headers: Authorization: Bearer <JWT>
    Body: multipart/form-data with 'image' file
    Returns: JSON with estimated macros/calories
    """
    current_user = request.current_user
    
    if "image" not in request.files:
        return jsonify({"error": "No image provided"}), 400

    image_file = request.files["image"]
    image_bytes = image_file.read()
    encoded_image = encode_image(image_bytes)
    
    if not encoded_image:
        return jsonify({"error": "Failed to encode image"}), 500

    # Get prediction from OpenAI
    openai_response = get_openai_prediction(encoded_image)
    
    if not openai_response:
        return jsonify({"error": "Failed to get prediction from OpenAI"}), 500

    # Parse the response to extract macros
    macros = parse_openai_response(openai_response)
    
    if not macros:
        return jsonify({"error": "Failed to parse OpenAI response"}), 500

    # Prepare the document to store in MongoDB
    food_doc = {
        "user_id": str(current_user["_id"]),
        # "image_name": image_file.filename,  # Optionally store the image name
        # "image_data_b64": encoded_image,    # Optionally store the image data
        "analysis_result": macros,
        "created_at": datetime.now(timezone.utc)
    }

    try:
        insert_result = food_logs.insert_one(food_doc)
    except Exception as e:
        print(f"Error inserting into MongoDB: {e}")
        return jsonify({"error": "Failed to store analysis result"}), 500

    return jsonify({
        "message": "Food analysis complete",
        "food_id": str(insert_result.inserted_id),
        "analysis_result": macros
    }), 200

@app.route("/food_logs", methods=["GET"])
@token_required
def get_food_logs():
    """
    Endpoint: GET /food_logs
    Headers: Authorization: Bearer <JWT>
    Returns: JSON list of user's food logs
    """
    current_user = request.current_user
    try:
        logs_cursor = food_logs.find({"user_id": str(current_user["_id"])})
        logs = []
        for log in logs_cursor:
            logs.append({
                "food_id": str(log["_id"]),
                "analysis_result": log["analysis_result"],
                "created_at": log["created_at"]
            })
        return jsonify({"food_logs": logs}), 200
    except Exception as e:
        print(f"Error fetching food logs: {e}")
        return jsonify({"error": "Failed to fetch food logs"}), 500

@app.route("/food_logs/<food_id>", methods=["GET"])
@token_required
def get_food_log(food_id):
    """
    Endpoint: GET /food_logs/<food_id>
    Headers: Authorization: Bearer <JWT>
    Returns: JSON with specific food log details
    """
    current_user = request.current_user
    try:
        log = food_logs.find_one({"_id": ObjectId(food_id), "user_id": str(current_user["_id"])})
        if not log:
            return jsonify({"error": "Food log not found."}), 404
        
        return jsonify({
            "food_id": str(log["_id"]),
            "analysis_result": log["analysis_result"],
            "created_at": log["created_at"]
        }), 200
    except Exception as e:
        print(f"Error fetching food log: {e}")
        return jsonify({"error": "Failed to fetch food log"}), 500

# Additional routes like updating or deleting food logs can be added similarly,
# ensuring they are protected by the @token_required decorator and verifying ownership.

if __name__ == "__main__":
    app.run(debug=True)