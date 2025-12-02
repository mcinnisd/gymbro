# app/chats/routes.py
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime, timezone
from app.supabase_client import supabase
import logging

chats_bp = Blueprint('chats', __name__)
logger = logging.getLogger(__name__)

@chats_bp.route("/", methods=["GET"], strict_slashes=False)
@jwt_required()
def get_chats():
    user_id = get_jwt_identity()
    try:
        response = supabase.table("chats").select("*").eq("user_id", user_id).execute()
        chats = response.data if response.data else []
        return jsonify({"chats": chats}), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching chats: {e}")
        return jsonify({"error": "Failed to fetch chats."}), 500

@chats_bp.route("/", methods=["POST"], strict_slashes=False)
@jwt_required()
def create_chat():
    user_id = get_jwt_identity()
    data = request.get_json()
    title = data.get("title", "New Chat")
    
    chat_doc = {
        "user_id": int(user_id),  # adjust if user_id is numeric in your Supabase table
        "title": title,
        "messages": [],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    
    try:
        response = supabase.table("chats").insert(chat_doc).execute()
        if response.data:
            return jsonify({"message": "Chat created successfully.", "chat_id": response.data[0]["id"]}), 201
        else:
            return jsonify({"error": "Failed to create chat."}), 500
    except Exception as e:
        current_app.logger.error(f"Error creating chat: {e}")
        return jsonify({"error": "Failed to create chat."}), 500

@chats_bp.route("/<int:chat_id>", methods=["GET"], strict_slashes=False)
@jwt_required()
def get_chat(chat_id):
    user_id = get_jwt_identity()
    try:
        response = supabase.table("chats").select("*").eq("id", chat_id).eq("user_id", user_id).execute()
        if response.data and len(response.data) > 0:
            chat = response.data[0]
            return jsonify({"chat": chat}), 200
        else:
            return jsonify({"error": "Chat not found."}), 404
    except Exception as e:
        current_app.logger.error(f"Error fetching chat ID {chat_id}: {e}")
        return jsonify({"error": "Failed to fetch chat."}), 500

@chats_bp.route("/<int:chat_id>/messages", methods=["POST"], strict_slashes=False)
@jwt_required()
def send_message(chat_id):
    try:
        user_id = get_jwt_identity()
    except Exception as e:
        logger.error(f"Error retrieving user identity: {e}")
        return jsonify({"error": "Invalid user identity."}), 400

    try:
        response = supabase.table("chats").select("*").eq("id", chat_id).eq("user_id", user_id).execute()
        if not response.data or len(response.data) == 0:
            logger.warning(f"Chat ID {chat_id} not found for user ID {user_id}")
            return jsonify({"error": "Chat not found."}), 404
        chat = response.data[0]
    except Exception as e:
        logger.error(f"Error fetching chat ID {chat_id}: {e}")
        return jsonify({"error": "Failed to fetch chat."}), 500

    data = request.get_json()
    user_message = data.get("message")
    if not user_message:
        logger.warning(f"Empty message received for chat ID {chat_id} by user ID {user_id}")
        return jsonify({"error": "Message content is required."}), 400

    user_msg_doc = {
        "sender": "user",
        "content": user_message,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

    try:
        current_messages = chat.get("messages", [])
        updated_messages = current_messages + [user_msg_doc]
        supabase.table("chats").update({
            "messages": updated_messages,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }).eq("id", chat_id).execute()
        logger.info(f"User message appended to chat ID {chat_id}")
    except Exception as e:
        logger.error(f"Error appending user message to chat ID {chat_id}: {e}")
        return jsonify({"error": "Failed to append message."}), 500

    # Prepare messages for the chatbot API
    all_messages = updated_messages
    openai_messages = [
        {"role": "user" if msg["sender"] == "user" else "assistant", "content": msg["content"]}
        for msg in all_messages
    ]

    try:
        from app.utils.openai_utils import generate_chat_response
        bot_reply = generate_chat_response(messages=openai_messages)
        logger.info(f"Bot reply generated for chat ID {chat_id}")
    except Exception as e:
        logger.error(f"Error generating bot reply for chat ID {chat_id}: {e}")
        return jsonify({"error": "Failed to get response from chatbot."}), 500

    bot_msg_doc = {
        "sender": "bot",
        "content": bot_reply,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    try:
        updated_messages.append(bot_msg_doc)
        supabase.table("chats").update({
            "messages": updated_messages,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }).eq("id", chat_id).execute()
        logger.info(f"Bot message appended to chat ID {chat_id}")
    except Exception as e:
        logger.error(f"Error appending bot message to chat ID {chat_id}: {e}")
        return jsonify({"error": "Failed to append bot message."}), 500

    return jsonify({"reply": bot_reply}), 200