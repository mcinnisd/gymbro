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
        
        context_text = ""
        chart_data = None
        
        try:
            from app.context.intent_detector import hybrid_detect_intent, needs_context, IntentType, extract_chart_metric, detect_chart_scope
            from app.context.context_builder import build_context, format_context_for_prompt
            from app.context.chart_generator import generate_chart_data
            
            # Intent Detection
            yield f"data: {json.dumps({'status': 'Analyzing request...'})}\n\n"
            intent = hybrid_detect_intent(user_message)
            logger.info(f"Detected intent: {intent.intent_type.value} (conf: {intent.confidence})")
            
            # Chart Handling
            if intent.is_chart_request:
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
            
            # Check for Council Trigger
            if user_message.strip().lower().startswith("/council"):
                # Use Council of Coaches
                from app.context.council_service import CouncilService
                
                # Build context first
                yield f"data: {json.dumps({'status': 'Gathering context for the Council...'})}\n\n"
                context_data = build_context(user_id, intent)
                context_str = format_context_for_prompt(context_data)
                
                def generate_council_stream():
                    # Initial status
                    yield f"data: {json.dumps({'status': 'Summoning the Council of Coaches...'})}\n\n"
                    
                    # Get synthesized response (blocking for now)
                    council_response = CouncilService.get_council_advice(user_id, user_message, context_str)
                    
                    # Stream the response chunk by chunk
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
                    try:
                        final_messages = updated_messages + [bot_msg_doc]
                        supabase.table("chats").update({
                            "messages": final_messages,
                            "updated_at": datetime.now(timezone.utc).isoformat()
                        }).eq("id", chat_id).execute()
                    except Exception as e:
                        logger.error(f"Error saving council message: {e}")

                # Yield from the council stream
                yield from generate_council_stream()
                return # End the main generator

            # Context Building
            if needs_context(intent):
                yield f"data: {json.dumps({'status': 'Gathering context...'})}\n\n"
                context_data = build_context(user_id, intent)
                if context_data:
                    context_text = format_context_for_prompt(context_data)
                    # Truncate context to avoid overflow (approx 1000 tokens)
                    if len(context_text) > 4000:
                        context_text = context_text[:4000] + "\n...(truncated)"
        except Exception as e:
            logger.error(f"Context error: {e}")
            # Continue without context
        
            # Proposal Instruction
            proposal_instruction = """
            To modify the calendar, you must output a JSON object (no markdown) in this format:
            {
                "type": "proposal",
                "action": "create_event" | "update_event" | "delete_event",
                "data": { ... arguments ... },
                "reasoning": "Short explanation"
            }
            For 'create_event', data must have: 
                - date (YYYY-MM-DD)
                - title (string)
                - event_type: MUST be one of: "run", "strength", "rest", "race", "other"
                - description (string)
            For 'update_event', data must have: event_id, updates (dict).
            For 'delete_event', data must have: event_id.
            """
            context_text = f"{context_text}\n\n{proposal_instruction}"

            # Generate Response
            yield f"data: {json.dumps({'status': 'Writing response...'})}\n\n"
            
            try:
                from app.utils.llm_utils import generate_chat_response
                
                user_response = supabase.table("users").select("goals").eq("id", user_id).execute()
                llm_provider = None
                if user_response.data:
                    llm_provider = user_response.data[0].get("goals", {}).get("llm_model")
                logger.info(f"Using LLM provider from user prefs: {llm_provider}")

                # Call LLM (Stream=True to get text, but we need to buffer to check for JSON)
                # For simplicity with Local LLMs, we'll disable streaming for the initial generation to parse JSON reliably
                # Call LLM with streaming enabled
                stream_gen = generate_chat_response(
                    messages=openai_messages, 
                    mode="coach", 
                    provider=llm_provider,
                    context=context_text,
                    stream=True 
                )
                
                response_text = ""
                # Stream it out to the user and buffer it
                for chunk in stream_gen:
                    if chunk:
                        response_text += chunk
                        yield f"data: {json.dumps({'token': chunk})}\n\n"
                
                # Check for JSON Proposal
                import re
                proposal = None
                clean_text = response_text.strip()
                
                # Strip markdown code blocks if present
                if "```json" in clean_text:
                    clean_text = re.sub(r'^```json\s*', '', clean_text)
                    clean_text = re.sub(r'\s*```.*$', '', clean_text, flags=re.DOTALL)
                elif "```" in clean_text:
                    clean_text = re.sub(r'^```\s*', '', clean_text)
                    clean_text = re.sub(r'\s*```.*$', '', clean_text, flags=re.DOTALL)
                
                # Try to find JSON block
                json_match = re.search(r'\{.*\}', clean_text, re.DOTALL)
                if json_match:
                    try:
                        data = json.loads(json_match.group(0))
                        # Accept type: proposal OR type: create_event/update_event/delete_event
                        if data.get("type") in ["proposal", "create_event", "update_event", "delete_event"]:
                            # Normalize to proposal format
                            if data.get("type") != "proposal":
                                data["action"] = data["type"]
                                data["type"] = "proposal"
                            proposal = data
                    except:
                        pass
                
                if proposal:
                    # Send proposal to frontend
                    yield f"data: {json.dumps({'proposal': proposal})}\n\n"
                    
                    # Save as a special message type or just text?
                    # Let's save the reasoning as text, and the proposal in metadata
                    final_content = proposal.get("reasoning", "I have a proposal for your calendar.")
                    bot_msg_doc = {
                        "sender": "bot",
                        "content": final_content,
                        "proposal": proposal,
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    }
                else:
                    bot_msg_doc = {
                        "sender": "bot",
                        "content": response_text,
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    }
                
                if chart_data:
                    bot_msg_doc["chart_data"] = chart_data
                    
                try:
                    final_messages = updated_messages + [bot_msg_doc]
                    supabase.table("chats").update({
                        "messages": final_messages,
                        "updated_at": datetime.now(timezone.utc).isoformat()
                    }).eq("id", chat_id).execute()
                    
                    # Async extraction of intelligence (facts, goals, preferences)
                    # For now, we call it synchronously but handle errors
                    try:
                        from app.context.intelligence_service import IntelligenceService
                        IntelligenceService.extract_and_store(user_id, user_message, response_text)
                    except Exception as intel_err:
                        logger.warning(f"Failed to extract intelligence: {intel_err}")
                        
                except Exception as e:
                    logger.error(f"Error saving bot message: {e}")
                
                yield f"data: {json.dumps({'done': True})}\n\n"
                
            except Exception as e:
                logger.error(f"LLM error: {e}")
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
            
        # Parse result (it returns JSON string)
        result_data = json.loads(result)
        
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