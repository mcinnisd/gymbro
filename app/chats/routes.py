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

@chats_bp.route("/<int:chat_id>", methods=["DELETE"], strict_slashes=False)
@jwt_required()
def delete_chat(chat_id):
    try:
        user_id = get_jwt_identity()
        logger.info(f"Delete request received for chat {chat_id} by user {user_id}")
        
        # Check if this is the interview chat
        user_res = supabase.table("users").select("interview_chat_id").eq("id", user_id).execute()
        if user_res.data:
            interview_chat_id = user_res.data[0].get("interview_chat_id")
            logger.info(f"User's interview_chat_id: {interview_chat_id}, deleting chat_id: {chat_id}")
            if interview_chat_id and str(interview_chat_id) == str(chat_id):
                # Reset interview status
                logger.info(f"Deleting the active interview chat. Resetting user {user_id} status.")
                supabase.table("users").update({
                    "interview_chat_id": None,
                    "coach_status": "not_started",
                    "interview_step": 1
                }).eq("id", user_id).execute()

        # Verify ownership and delete
        res = supabase.table("chats").delete().eq("id", chat_id).eq("user_id", user_id).execute()
        
        if res.data:
            logger.info(f"Successfully deleted chat {chat_id}")
            return jsonify({"message": "Chat deleted successfully."}), 200
        else:
            logger.warning(f"Chat {chat_id} not found or denied for user {user_id}")
            return jsonify({"error": "Chat not found or access denied."}), 404
            
    except Exception as e:
        logger.error(f"Error deleting chat {chat_id}: {e}")
        return jsonify({"error": "Failed to delete chat."}), 500

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
    
    # --- AUTO-SYNC CHECK ---
    try:
        from app.garmin.routes import sync_if_needed
        sync_if_needed(user_id)
    except Exception as e:
        logger.error(f"Failed to trigger auto-sync check: {e}")
    
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

    # --- INTERVIEW HANDLING ---
    if chat.get("type") == "interview":
        try:
            from app.coach.interview_service import process_answer, get_next_question
            
            # 1. Process the answer (stores context)
            process_answer(user_id, user_message)
            
            # 2. Get next question (Dynamic LLM-driven)
            next_q_result = get_next_question(user_id, chat_id=chat_id)
            
            if next_q_result.get("success"):
                bot_message = next_q_result.get("question")
                is_complete = next_q_result.get("is_complete", False)
                
                # Save bot message
                bot_msg_doc = {
                    "sender": "bot",
                    "content": bot_message,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "is_interview_complete": is_complete
                }
                
                final_messages = updated_messages + [bot_msg_doc]
                supabase.table("chats").update({
                    "messages": final_messages,
                    "updated_at": datetime.now(timezone.utc).isoformat()
                }).eq("id", chat_id).execute()
                
                # If complete, update user status
                if is_complete:
                    supabase.table("users").update({
                        "coach_status": "interview_completed",
                        "interview_completed_at": datetime.now(timezone.utc).isoformat()
                    }).eq("id", user_id).execute()
                
                return jsonify({
                    "message": bot_message,
                    "is_complete": is_complete
                }), 200
            else:
                logger.error(f"Interview service error: {next_q_result.get('error')}")
                # Fallback to normal chat if interview service fails
        except Exception as e:
            logger.error(f"Error in interview handling: {e}")
            # Fallback to normal chat


    def generate():
        # Yield initial thinking status
        yield f"data: {json.dumps({'status': 'Thinking...'})}\n\n"
        
        try:
            from app.agent.analyst import AnalystAgent
            from app.context.context_builder import build_context, format_context_for_prompt
            from app.context.intent_detector import hybrid_detect_intent # Keeping for context building
            
            # --- COUNCIL CHECK ---
            if user_message.strip().lower().startswith("/council"):
                 # Use Council of Coaches (Keeping legacy path for Council for now)
                from app.context.council_service import CouncilService
                from app.context.intent_detector import hybrid_detect_intent
                
                # Build context first
                intent = hybrid_detect_intent(user_message)
                yield f"data: {json.dumps({'status': 'Summoning the Council of Coaches...'})}\n\n"
                context_data = build_context(user_id, intent)
                context_str = format_context_for_prompt(context_data)
                
                council_response = CouncilService.get_council_advice(user_id, user_message, context_str)
                
                # Stream the response chunk by chunk (simulate stream for council)
                yield f"data: {json.dumps({'status': 'The Council has spoken'})}\n\n"
                
                chunk_size = 50
                for i in range(0, len(council_response), chunk_size):
                    chunk = council_response[i:i+chunk_size]
                    yield f"data: {json.dumps({'token': chunk})}\n\n"
                    import time
                    time.sleep(0.05)
                
                yield f"data: {json.dumps({'done': True})}\n\n"
                
                # Save bot message
                bot_msg_doc = {
                    "sender": "bot",
                    "content": council_response,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
                supabase.table("chats").update({
                    "messages": updated_messages + [bot_msg_doc],
                    "updated_at": datetime.now(timezone.utc).isoformat()
                }).eq("id", chat_id).execute()
                return

            # --- ANALYST AGENT FLOW ---
            
            # 1. Build Context (Optional but helpful for the agent)
            # We can still use intent detector just to grab relevant context
            intent = hybrid_detect_intent(user_message)
            context_data = build_context(user_id, intent)
            context_text = format_context_for_prompt(context_data)
            
            user_response = supabase.table("users").select("goals").eq("id", user_id).execute()
            llm_provider = None
            if user_response.data:
                llm_provider = user_response.data[0].get("goals", {}).get("llm_model")
            
            # 2. Run Agent
            # Pass llm_provider as the 'provider' argument, NOT 'model_name'
            agent = AnalystAgent(provider=llm_provider)
            gen = agent.run(user_id=user_id, message=user_message, context=context_text)
            
            final_response_text = ""
            chart_data = None
            
            for update in gen:
                # Handle Status Updates
                if "status" in update:
                    yield f"data: {json.dumps({'status': update['status']})}\n\n"
                
                # Handle Chart Data (if passed through or we catch it)
                # Currently Agent doesn't yield 'chart' explicitly, but we can detect it or 
                # modify agent to yield 'data' payload.
                # For now, let's assume if the text contains chart info, we might need a parser later.
                # Actually, let's check if the update has a 'chart' key (future proofing)
                if "chart" in update:
                     chart_data = update["chart"]
                     yield f"data: {json.dumps({'chart': chart_data})}\n\n"

                # Handle Final Answer Text
                if "answer" in update:
                    # Stream the answer token by token?
                    # The Agent yields the full answer string currently.
                    # We can split it to simulate streaming or just send it.
                    answer = update["answer"]
                    final_response_text = answer
                    
                    # Simulate streaming for UX
                    words = answer.split(" ")
                    for word in words:
                        yield f"data: {json.dumps({'token': word + ' '})}\n\n"
                        import time
                        time.sleep(0.02)
            
            # 3. Save to DB
            bot_msg_doc = {
                "sender": "bot",
                "content": final_response_text,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            if chart_data:
                bot_msg_doc["chart_data"] = chart_data
                
            final_messages = updated_messages + [bot_msg_doc]
            supabase.table("chats").update({
                "messages": final_messages,
                "updated_at": datetime.now(timezone.utc).isoformat()
            }).eq("id", chat_id).execute()
            
            # 4. Async Learning
            try:
                from app.context.intelligence_service import IntelligenceService
                IntelligenceService.extract_and_store(user_id, user_message, final_response_text)
            except Exception as intel_err:
                logger.warning(f"Failed to extract intelligence: {intel_err}")

            yield f"data: {json.dumps({'done': True})}\n\n"

        except Exception as e:
            logger.error(f"Agent error: {e}")
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return Response(stream_with_context(generate()), mimetype='text/event-stream')


@chats_bp.route("/<chat_id>/actions", methods=["POST"], strict_slashes=False)
@jwt_required()
def execute_action(chat_id):
    """
    Execute a proposed action (e.g., create_event) approved by the user.
    """
    user_id = get_jwt_identity()
    data = request.get_json()
    action = data.get("action")
    action_data = data.get("data")
    
    if not action or not action_data:
        return jsonify({"error": "Invalid action data."}), 400
        
    try:
        from app.tools.calendar_tools import create_event, update_event, delete_event
        
        result = None
        if action == "create_event":
            result = create_event(user_id, **action_data)
        elif action == "update_event":
            result = update_event(user_id, **action_data)
        elif action == "delete_event":
            result = delete_event(user_id, **action_data)
        else:
            return jsonify({"error": "Unknown action."}), 400
            
        # Parse result (it is now a dict)
        result_data = result
        
        if result_data.get("status") == "success":
            # Add a system message to chat confirming action
            try:
                # Fetch chat
                chat_res = supabase.table("chats").select("messages").eq("id", chat_id).execute()
                if chat_res.data:
                    messages = chat_res.data[0]["messages"]
                    sys_msg = {
                        "sender": "system",
                        "content": f"Action completed: {result_data.get('message')}",
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    }
                    supabase.table("chats").update({
                        "messages": messages + [sys_msg],
                        "updated_at": datetime.now(timezone.utc).isoformat()
                    }).eq("id", chat_id).execute()
            except Exception as e:
                logger.error(f"Error updating chat with action confirmation: {e}")
                
            return jsonify(result_data), 200
        else:
            return jsonify(result_data), 400
            
    except Exception as e:
        logger.error(f"Error executing action: {e}")
        return jsonify({"error": str(e)}), 500