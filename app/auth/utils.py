from functools import wraps
from flask import request, jsonify
from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity
from app.supabase_client import supabase

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if request.method == 'OPTIONS':
            return f(*args, **kwargs)
            
        try:
            verify_jwt_in_request()
            user_identity = get_jwt_identity()
            # user_identity is the 'sub' claim, which we set to user_id (int) or uuid?
            # In login, we used create_access_token(identity=user_id)
            
            # Fetch user from DB to ensure valid and get details
            # Assuming identity is the ID
            response = supabase.table("users").select("*").eq("id", user_identity).execute()
            if not response.data:
                return jsonify({"error": "User not found"}), 401
                
            current_user = response.data[0]
            
            # Attach to request for easy access
            request.current_user = current_user
            
            # Pass current_user to the function if it expects it?
            # The previous implementation in activities/routes.py did NOT pass it as argument
            # but set request.current_user.
            # However, my new analytics route expects `current_user` as argument.
            # Let's standardize: Do NOT pass as argument, use request.current_user.
            # But wait, my analytics route definition: def get_analytics_summary(current_user):
            # So I should pass it if the function signature asks for it?
            # Or just update analytics route to use request.current_user.
            
            return f(*args, **kwargs)
            
        except Exception as e:
            return jsonify({"error": "Token is invalid or missing", "details": str(e)}), 401
            
    return decorated
