# app/chats/routes.py
from flask import Blueprint, request, jsonify, current_app, Response, stream_with_context
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime, timezone
from app.supabase_client import supabase
import logging
import json

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

@chats_bp.route("/<chat_id>/messages", methods=["POST"], strict_slashes=False)
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

    # Save user message immediately
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
    # Limit to last 10 messages to save context
    recent_messages = updated_messages[-10:] if len(updated_messages) > 10 else updated_messages
    openai_messages = [
        {"role": "user" if msg["sender"] == "user" else "assistant", "content": msg["content"]}
        for msg in recent_messages
    ]

    def generate():
        # Yield initial thinking status
        yield f"data: {json.dumps({'status': 'Thinking...'})}\n\n"
        
        context_text = ""
        chart_data = None
        
        try:
            from app.context.intent_detector import detect_intent, needs_context, IntentType, extract_chart_metric, detect_chart_scope
            from app.context.context_builder import build_context, format_context_for_prompt
            from app.context.chart_generator import generate_chart_data
            
            # Intent Detection
            yield f"data: {json.dumps({'status': 'Analyzing request...'})}\n\n"
            intent = detect_intent(user_message)
            logger.info(f"Detected intent: {intent.intent_type.value}")
            
            # Handle Chart Requests
            if intent.intent_type == IntentType.CHART_REQUEST:
                yield f"data: {json.dumps({'status': 'Generating chart...'})}\n\n"
                metric = extract_chart_metric(user_message)
                scope = detect_chart_scope(user_message)
                logger.info(f"Generating chart for metric: {metric}, scope: {scope}")
                
                encryption_key = current_app.config.get("ENCRYPTION_KEY")
                
                chart_data = generate_chart_data(
                    user_id=user_id, 
                    metric=metric,
                    scope=scope,
                    encryption_key=encryption_key,
                    message=user_message
                )
                if chart_data:
                    yield f"data: {json.dumps({'chart': chart_data})}\n\n"
            
            # Context Building
            if needs_context(intent):
                yield f"data: {json.dumps({'status': 'Gathering context...'})}\n\n"
                context = build_context(user_id, intent)
                if context:
                    context_text = format_context_for_prompt(context)
                    # Truncate context to avoid overflow (approx 1000 tokens)
                    if len(context_text) > 4000:
                        context_text = context_text[:4000] + "\n...(truncated)"
        except Exception as e:
            logger.error(f"Context error: {e}")
            # Continue without context
        
        # Generate Response
        yield f"data: {json.dumps({'status': 'Writing response...'})}\n\n"
        
        try:
            from app.utils.llm_utils import generate_chat_response
            user_response = supabase.table("users").select("goals").eq("id", user_id).execute()
            llm_provider = None
            if user_response.data:
                llm_provider = user_response.data[0].get("goals", {}).get("llm_model")

            response_generator = generate_chat_response(
                messages=openai_messages, 
                mode="coach", 
                provider=llm_provider,
                context=context_text,
                stream=True
            )
            
            full_response = ""
            for chunk in response_generator:
                if chunk:
                    full_response += chunk
                    yield f"data: {json.dumps({'token': chunk})}\n\n"
            
            # Save bot message to DB
            bot_msg_doc = {
                "sender": "bot",
                "content": full_response,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            if chart_data:
                bot_msg_doc["chart_data"] = chart_data
                
            try:
                # Re-fetch chat to get latest state (in case of race conditions, though unlikely in this flow)
                # Ideally we lock or use atomic updates, but appending to list is tricky in Supabase without stored proc
                # For now, we append to what we had + user msg
                final_messages = updated_messages + [bot_msg_doc]
                supabase.table("chats").update({
                    "messages": final_messages,
                    "updated_at": datetime.now(timezone.utc).isoformat()
                }).eq("id", chat_id).execute()
            except Exception as e:
                logger.error(f"Error saving bot message: {e}")
                
            yield f"data: {json.dumps({'done': True})}\n\n"
            
        except Exception as e:
            logger.error(f"LLM error: {e}")
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return Response(stream_with_context(generate()), mimetype='text/event-stream')