# app/chats/routes.py

from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime, timezone, UTC
from bson import ObjectId
from app.utils.openai_utils import generate_chat_response  # New import
from app.extensions import mongo, limiter
from app.config import Config
import logging

chats_bp = Blueprint('chats', __name__)

# Configure logger
logger = logging.getLogger(__name__)

@chats_bp.route("/", methods=["GET"], strict_slashes=False)
@jwt_required()
def get_chats():
    """
    Get all chats for the logged-in user.
    """
    try:
        user_identity = get_jwt_identity()
        current_app.logger.info(f"Fetching chats for user ID: {user_identity}")
        user_id = ObjectId(user_identity)
    except Exception as e:
        current_app.logger.error(f"Error retrieving user identity: {e}")
        return jsonify({"error": "Invalid user identity."}), 400

    try:
        chats = mongo.db.chats.find({"user_id": user_id})
        chats_list = []
        for chat in chats:
            chats_list.append({
                "id": str(chat["_id"]),
                "title": chat.get("title", "Untitled Chat"),
                "created_at": chat["created_at"].isoformat(),
                "updated_at": chat["updated_at"].isoformat()
            })
        return jsonify({"chats": chats_list}), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching chats: {e}")
        return jsonify({"error": "Failed to fetch chats."}), 500

@chats_bp.route("/", methods=["POST"], strict_slashes=False)
@jwt_required()
def create_chat():
    """
    Create a new chat for the logged-in user.
    """
    try:
        user_identity = get_jwt_identity()
        current_app.logger.info(f"Creating chat for user ID: {user_identity}")
        user_id = ObjectId(user_identity)
    except Exception as e:
        current_app.logger.error(f"Error retrieving user identity: {e}")
        return jsonify({"error": "Invalid user identity."}), 400

    data = request.get_json()
    title = data.get("title", "New Chat")
    
    chat_doc = {
        "user_id": user_id,
        "title": title,
        "messages": [],
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc)
    }
    
    try:
        result = mongo.db.chats.insert_one(chat_doc)
        current_app.logger.info(f"Chat created with ID: {result.inserted_id}")
        return jsonify({"message": "Chat created successfully.", "chat_id": str(result.inserted_id)}), 201
    except Exception as e:
        current_app.logger.error(f"Error creating chat: {e}")
        return jsonify({"error": "Failed to create chat."}), 500

@chats_bp.route("/<chat_id>", methods=["GET"], strict_slashes=False)
@jwt_required()
def get_chat(chat_id):
    """
    Get a specific chat's messages.
    """
    try:
        user_identity = get_jwt_identity()
        current_app.logger.info(f"Fetching chat ID: {chat_id} for user ID: {user_identity}")
        user_id = ObjectId(user_identity)
    except Exception as e:
        current_app.logger.error(f"Error retrieving user identity: {e}")
        return jsonify({"error": "Invalid user identity."}), 400

    try:
        chat = mongo.db.chats.find_one({"_id": ObjectId(chat_id), "user_id": user_id})
        
        if not chat:
            current_app.logger.warning(f"Chat ID: {chat_id} not found for user ID: {user_identity}")
            return jsonify({"error": "Chat not found."}), 404
        
        # Convert ObjectId to string and datetime to ISO format
        messages = [{
            "sender": msg["sender"],
            "content": msg["content"],
            "timestamp": msg["timestamp"].isoformat()
        } for msg in chat.get("messages", [])]
        
        chat_info = {
            "id": str(chat["_id"]),
            "title": chat.get("title", "Untitled Chat"),
            "messages": messages,
            "created_at": chat["created_at"].isoformat(),
            "updated_at": chat["updated_at"].isoformat()
        }
        
        return jsonify({"chat": chat_info}), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching chat ID: {chat_id}: {e}")
        return jsonify({"error": "Failed to fetch chat."}), 500

@chats_bp.route("/<chat_id>/messages", methods=["POST"], strict_slashes=False)
@jwt_required()
@limiter.limit("10 per minute")
def send_message(chat_id):
    """
    Send a message in a specific chat and get a response from the chatbot.
    """
    try:
        user_identity = get_jwt_identity()
        logger.info(f"User ID: {user_identity} sending message to chat ID: {chat_id}")
        user_id = ObjectId(user_identity)
    except Exception as e:
        logger.error(f"Error retrieving user identity: {e}")
        return jsonify({"error": "Invalid user identity."}), 400

    try:
        chat = mongo.db.chats.find_one({"_id": ObjectId(chat_id), "user_id": user_id})
        if not chat:
            logger.warning(f"Chat ID: {chat_id} not found for user ID: {user_identity}")
            return jsonify({"error": "Chat not found."}), 404
    except Exception as e:
        logger.error(f"Error fetching chat ID: {chat_id}: {e}")
        return jsonify({"error": "Failed to fetch chat."}), 500

    data = request.get_json()
    user_message = data.get("message")

    if not user_message:
        logger.warning(f"Empty message received for chat ID: {chat_id} by user ID: {user_identity}")
        return jsonify({"error": "Message content is required."}), 400

    # Append user's message to chat
    user_msg_doc = {
        "sender": "user",
        "content": user_message,
        "timestamp": datetime.now(UTC)
    }

    try:
        mongo.db.chats.update_one(
            {"_id": ObjectId(chat_id)},
            {"$push": {"messages": user_msg_doc}, "$set": {"updated_at": datetime.now(UTC)}}
        )
        logger.info(f"User message appended to chat ID: {chat_id}")
    except Exception as e:
        logger.error(f"Error appending user message to chat ID: {chat_id}: {e}")
        return jsonify({"error": "Failed to append message."}), 500

    # Prepare messages for OpenAI API
    existing_messages = chat.get("messages", [])
    # Include the new user message
    all_messages = existing_messages + [user_msg_doc]

    # Transform messages to OpenAI format
    openai_messages = []
    for msg in all_messages:
        role = "user" if msg["sender"] == "user" else "assistant"
        openai_messages.append({"role": role, "content": msg["content"]})

    # Optionally, decide the mode based on certain criteria
    # For simplicity, we'll use "normal" mode here
    mode = "normal"  # Change to "developer" as needed

    try:
        bot_reply = generate_chat_response(messages=openai_messages)
        logger.info(f"Bot reply generated for chat ID: {chat_id}")
    except Exception as e:
        logger.error(f"Error generating bot reply for chat ID: {chat_id}: {e}")
        return jsonify({"error": "Failed to get response from chatbot."}), 500

    # Append bot's reply to chat
    bot_msg_doc = {
        "sender": "bot",
        "content": bot_reply,
        "timestamp": datetime.now(UTC)
    }

    try:
        mongo.db.chats.update_one(
            {"_id": ObjectId(chat_id)},
            {"$push": {"messages": bot_msg_doc}, "$set": {"updated_at": datetime.now(UTC)}}
        )
        logger.info(f"Bot message appended to chat ID: {chat_id}")
    except Exception as e:
        logger.error(f"Error appending bot message to chat ID: {chat_id}: {e}")
        return jsonify({"error": "Failed to append bot message."}), 500

    return jsonify({"reply": bot_reply}), 200