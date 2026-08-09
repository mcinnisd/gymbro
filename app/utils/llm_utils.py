from google import genai as google_genai
from google.genai import types as google_genai_types
from openai import OpenAI
from flask import current_app
from app.config import Config
import logging
import json
from typing import List, Optional

# Configure logger
logger = logging.getLogger(__name__)

_gemini_client = None

def get_gemini_client():
    global _gemini_client
    if _gemini_client is not None:
        return _gemini_client
        
    if Config.USE_VERTEX_AI:
        logger.info(f"Initializing Google GenAI Client with Vertex AI (project={Config.GOOGLE_CLOUD_PROJECT}, location={Config.GOOGLE_CLOUD_LOCATION})")
        _gemini_client = google_genai.Client(
            vertexai=True,
            project=Config.GOOGLE_CLOUD_PROJECT,
            location=Config.GOOGLE_CLOUD_LOCATION
        )
    else:
        logger.info("Initializing Google GenAI Client with Gemini API (API Key)")
        _gemini_client = google_genai.Client(api_key=Config.GEMINI_API_KEY)
    return _gemini_client

def generate_chat_response(messages, model_name=None, mode="normal", system_prompt=None, provider=None, context=None, stream=False, tools=None):
    """
    Generate a chat response from the configured LLM provider.

    Args:
        messages (list): List of message dictionaries with 'role' and 'content'.
        model_name (str): Model name (ignored if using local LLM default).
        mode (str): Prompting mode ('normal', 'developer', 'coach').
        system_prompt (str): Custom system prompt to override/prepend.
        provider (str): Optional provider override ('local', 'openai', 'gemini').
        context (str): Optional user fitness context to inject into system prompt.
        stream (bool): If True, returns a generator yielding text chunks.
        tools (list): Optional list of tools for function calling (OpenAI only).

    Returns:
        str or generator or ToolCalls: The generated chatbot response.
    """
    if not provider:
        provider = Config.LLM_PROVIDER
        
    # Dynamically resolve provider and model names if a specific model identifier is passed as 'provider'
    if provider:
        provider_lower = provider.lower()
        if "gemini" in provider_lower:
            model_name = provider
            provider = "gemini"
        elif "gpt" in provider_lower:
            model_name = provider
            provider = "openai"
        elif "grok" in provider_lower or "xai" in provider_lower:
            model_name = provider
            provider = "xai"
    
    logger.info(f"Using LLM provider: {provider} (model: {model_name})")
    
    # Prepare system instruction
    system_instruction = system_prompt
    if not system_instruction:

        if mode == "developer":
            system_instruction = "You are a helpful assistant that provides detailed and accurate answers."
        elif mode == "coach":
            system_instruction = """You are an expert running and fitness coach with deep knowledge of training methodology, physiology, and performance optimization.

CRITICAL RULES - YOU MUST FOLLOW THESE:

1. DATA ACCURACY:
   - ONLY cite numbers that appear EXACTLY in the [USER FITNESS CONTEXT] section below
   - If a metric isn't in the context, say "I don't have that data in your recent records"
   - Never estimate, round, or guess values - quote the EXACT numbers provided
   - When citing a value, mention its source (e.g., "Your RHR is 55 bpm based on Garmin data from Dec 1-7")

2. UNCERTAINTY:
   - If the user asks about something NOT in the context, clearly say "I don't have data for that"
   - If the data seems incomplete, ask clarifying questions
   - Don't make up year-over-year comparisons if the context shows no last-year data

3. REFERENCES:
   - When discussing specific activities, reference them by date and distance
   - Help users verify by pointing them to specific workouts

4. TONE:
   - Be encouraging but honest
   - Ask follow-up questions to understand goals better
   - Focus on actionable advice

63: Remember: Your credibility depends on accuracy. Never invent numbers."""
        else:
            system_instruction = "You are a helpful assistant."

    # Inject context into system prompt if provided
    if context and context.strip():
        system_instruction = f"{system_instruction}\n\n{context}"
        logger.debug(f"Context injected into system prompt ({len(context)} chars)")

    # --- DATE INJECTION ---
    # Always inject current date so LLM knows what "today" and "tomorrow" mean
    from datetime import datetime
    now = datetime.now()
    date_str = now.strftime("%Y-%m-%d")
    day_name = now.strftime("%A")
    tomorrow = (now + __import__('datetime').timedelta(days=1)).strftime("%Y-%m-%d")
    date_injection = f"[CURRENT DATE: {date_str}, {day_name}]\nWhen referencing dates, 'today' = {date_str}, 'tomorrow' = {tomorrow}.\n\n"
    system_instruction = date_injection + system_instruction

    # --- TOOL ADAPTER FOR LOCAL/GEMINI ---
    if tools and provider in ["local", "gemini"]:
        # Format tools into system prompt
        tools_desc = json.dumps(tools, indent=2)
        tool_instruction = f"""
You have access to the following tools:
{tools_desc}

To use a tool, you MUST output a JSON object in the following format ONLY, with no other text:
{{
  "tool_calls": [
    {{
      "id": "call_unique_id",
      "type": "function",
      "function": {{
        "name": "function_name",
        "arguments": "{{\\"arg1\\": \\"value1\\"}}"
      }}
    }}
  ]
}}

If you do not need to use a tool, just respond normally.
"""
        system_instruction = f"{system_instruction}\n\n{tool_instruction}"
        logger.info(f"Injected tool instructions for {provider}")

    # --- LOCAL LLM (Llama.cpp via OpenAI API) ---
    if provider == "local":
        try:
            client = OpenAI(
                base_url=Config.LOCAL_LLM_URL,
                api_key="sk-no-key-required"
            )
            
            # Construct messages list for OpenAI format
            openai_messages = []
            if system_instruction:
                openai_messages.append({"role": "system", "content": system_instruction})
            
            for msg in messages:
                if msg["role"] == "system" and system_instruction:
                    continue 
                openai_messages.append(msg)

            logger.info(f"Sending request to Local LLM at {Config.LOCAL_LLM_URL} (stream={stream})...")
            completion = client.chat.completions.create(
                model=Config.LOCAL_LLM_MODEL,
                messages=openai_messages,
                stream=stream
            )
            
            if stream:
                # For streaming, we need to buffer to check for tool calls, which is hard.
                # So if tools are enabled, we might want to disable streaming or check first chunk.
                # But for now, let's just yield. If it's a tool call, the frontend might show JSON.
                # Ideally, we should buffer.
                def generate():
                    for chunk in completion:
                        if chunk.choices[0].delta.content:
                            yield chunk.choices[0].delta.content
                return generate()
            else:
                content = completion.choices[0].message.content
                # Attempt to parse tool call
                try:
                    if tools and "tool_calls" in content:
                        # Find JSON block
                        import re
                        json_match = re.search(r'\{.*\}', content, re.DOTALL)
                        if json_match:
                            json_str = json_match.group(0)
                            data = json.loads(json_str)
                            if "tool_calls" in data:
                                # Create a fake message object with tool_calls
                                from types import SimpleNamespace
                                msg = SimpleNamespace()
                                msg.content = None
                                msg.tool_calls = []
                                for tc in data["tool_calls"]:
                                    # Ensure arguments are string
                                    args = tc["function"]["arguments"]
                                    if isinstance(args, dict):
                                        args = json.dumps(args)
                                    
                                    t_obj = SimpleNamespace()
                                    t_obj.id = tc.get("id", "call_1")
                                    t_obj.type = "function"
                                    t_obj.function = SimpleNamespace()
                                    t_obj.function.name = tc["function"]["name"]
                                    t_obj.function.arguments = args
                                    msg.tool_calls.append(t_obj)
                                return msg
                except Exception as e:
                    logger.warning(f"Failed to parse tool call from local LLM: {e}")
                
                return content

        except Exception as e:
            logger.error(f"Local LLM Error: {e}")
            return f"Error communicating with Local Coach: {e}"

    # --- OPENAI ---
    elif provider == "openai":
        if not Config.OPENAI_API_KEY:
            return "OpenAI API Key missing."

        try:
            client = OpenAI(api_key=Config.OPENAI_API_KEY)
            
            openai_messages = []
            if system_instruction:
                openai_messages.append({"role": "system", "content": system_instruction})
            
            for msg in messages:
                if msg["role"] == "system" and system_instruction:
                    continue
                openai_messages.append(msg)
                
            logger.info(f"Sending request to OpenAI ({Config.OPENAI_MODEL}) (stream={stream})...")
            
            completion = client.chat.completions.create(
                model=Config.OPENAI_MODEL,
                messages=openai_messages,
                stream=stream,
                tools=tools, # Pass tools if provided
                tool_choice="auto" if tools else None
            )
            
            if stream:
                if tools:
                    pass 

                def generate():
                    for chunk in completion:
                        if chunk.choices[0].delta.content:
                            yield chunk.choices[0].delta.content
                return generate()
            else:
                # Return the full message object if tools are used, to access tool_calls
                if tools:
                    return completion.choices[0].message
                return completion.choices[0].message.content
                
        except Exception as e:
            logger.error(f"OpenAI API Error: {e}")
            return f"Error communicating with OpenAI Coach: {e}"

    # --- GEMINI ---
    elif provider == "gemini":
        if not Config.USE_VERTEX_AI and not Config.GEMINI_API_KEY:
            return "Gemini API Key missing and Vertex AI not enabled."

        try:
            if not model_name or model_name.lower() == "gemini":
                if Config.USE_VERTEX_AI:
                    if tools or mode in ["agent", "coach"]:
                        model_name = "gemini-3.5-flash"
                    else:
                        model_name = "gemini-3.1-flash-lite"
                else:
                    model_name = "gemini-2.0-flash-exp"
                
            # Map model names for Vertex AI
            if Config.USE_VERTEX_AI:
                if model_name in ["gemini-3.5-flash", "gemini-3.1-flash-lite", "gemini-3.1-flash"]:
                    logger.info(f"Mapping Vertex AI model '{model_name}' to 'gemini-2.5-flash'")
                    model_name = "gemini-2.5-flash"

            client = get_gemini_client()

            gemini_history = []
            for msg in messages:
                if msg["role"] == "system":
                    continue
                gemini_role = "user" if msg["role"] == "user" else "model"
                gemini_history.append(
                    google_genai_types.Content(
                        role=gemini_role,
                        parts=[google_genai_types.Part.from_text(text=msg["content"])]
                    )
                )

            if not gemini_history:
                return "Error: No messages provided."

            last_message = gemini_history[-1]
            history_to_send = gemini_history[:-1]
            
            # Prepend dummy user turn if history starts with a model turn
            if history_to_send and history_to_send[0].role == "model":
                history_to_send.insert(0, google_genai_types.Content(role="user", parts=[google_genai_types.Part.from_text(text=" ")]))
            
            if last_message.role != "user":
                logger.warning("Last message in history is not from user.")
            
            config = google_genai_types.GenerateContentConfig(
                system_instruction=system_instruction
            )
            
            chat = client.chats.create(
                model=model_name,
                history=history_to_send,
                config=config
            )
            
            last_message_text = last_message.parts[0].text
            
            if stream:
                response = chat.send_message_stream(last_message_text)
                def generate():
                    for chunk in response:
                        if chunk.text:
                            yield chunk.text
                return generate()
            else:
                response = chat.send_message(last_message_text)
                content = response.text
                
                # Attempt to parse tool call (Same logic as Local)
                try:
                    if tools and "tool_calls" in content:
                        import re
                        json_match = re.search(r'\{.*\}', content, re.DOTALL)
                        if json_match:
                            json_str = json_match.group(0)
                            data = json.loads(json_str)
                            if "tool_calls" in data:
                                from types import SimpleNamespace
                                msg = SimpleNamespace()
                                msg.content = None
                                msg.tool_calls = []
                                for tc in data["tool_calls"]:
                                    args = tc["function"]["arguments"]
                                    if isinstance(args, dict):
                                        args = json.dumps(args)
                                    
                                    t_obj = SimpleNamespace()
                                    t_obj.id = tc.get("id", "call_1")
                                    t_obj.type = "function"
                                    t_obj.function = SimpleNamespace()
                                    t_obj.function.name = tc["function"]["name"]
                                    t_obj.function.arguments = args
                                    msg.tool_calls.append(t_obj)
                                return msg
                except Exception as e:
                    logger.warning(f"Failed to parse tool call from Gemini: {e}")
                
                return content

        except Exception as e:
            logger.error(f"Gemini API error: {e}")
            return f"Error communicating with Gemini Coach: {e}"

    # --- xAI (Grok) ---
    elif provider == "xai":
        if not Config.XAI_API_KEY:
            return "xAI API Key missing."

        try:
            client = OpenAI(
                base_url="https://api.x.ai/v1",
                api_key=Config.XAI_API_KEY,
                timeout=30.0
            )
            
            openai_messages = []
            if system_instruction:
                openai_messages.append({"role": "system", "content": system_instruction})
            
            for msg in messages:
                if msg["role"] == "system" and system_instruction:
                    continue
                openai_messages.append(msg)
                
            # Determine model to use
            model_to_use = Config.XAI_MODEL
            if model_name:
                 model_to_use = model_name
            
            # HARD FIX: Replace deprecated model if it appears (from env or old config)
            if model_to_use == "grok-beta":
                logger.warning("Replacing deprecated 'grok-beta' with 'grok-4-1-fast-non-reasoning'")
                model_to_use = "grok-4-1-fast-non-reasoning"

            logger.info(f"Sending request to xAI ({model_to_use}) (stream={stream})...")
            
            completion = client.chat.completions.create(
                model=model_to_use,
                messages=openai_messages,
                stream=stream,
                tools=tools,
                tool_choice="auto" if tools else None
            )
            
            if stream:
                def generate():
                    try:
                        chunk_count = 0
                        for chunk in completion:
                            chunk_count += 1
                            if chunk.choices[0].delta.content:
                                content = chunk.choices[0].delta.content
                                # logger.debug(f"Chunk {chunk_count}: {content}") # Verbose
                                yield content
                        if chunk_count == 0:
                            logger.warning("Stream ended with 0 chunks from xAI.")
                    except Exception as e:
                        logger.error(f"Error during xAI stream: {e}")
                        yield f" [Error: {str(e)}]"
                return generate()
            else:
                if tools:
                    return completion.choices[0].message
                return completion.choices[0].message.content
                
        except Exception as e:
            logger.error(f"xAI API Error: {e}")
            return f"Error communicating with xAI Coach: {e}"

    else:
        return f"Unknown LLM Provider: {provider}"


def get_embedding(text: str, provider: Optional[str] = None) -> Optional[List[float]]:
    """
    Generate embedding for text using the configured provider.
    Defaults to Gemini (768-dim) for cost-efficiency.
    """
    if not provider:
        provider = Config.EMBEDDING_PROVIDER
    
    text = text.replace("\n", " ") # Normalize
    
    # --- GEMINI EMBEDDINGS (768-dim) ---
    if provider == "gemini":
        if not Config.USE_VERTEX_AI and not Config.GEMINI_API_KEY:
            logger.warning("Gemini API Key missing and Vertex AI not enabled, cannot generate embedding.")
            return None
        try:
            client = get_gemini_client()
            model_name = Config.GEMINI_EMBEDDING_MODEL
            if Config.USE_VERTEX_AI and "embedding-001" in model_name:
                model_name = "gemini-embedding-001"
            response = client.models.embed_content(
                model=model_name,
                contents=text,
                config=google_genai_types.EmbedContentConfig(
                    output_dimensionality=768
                )
            )
            return response.embeddings[0].values
        except Exception as e:
            logger.error(f"Gemini embedding error: {e}")
            return None
            
    # --- OPENAI EMBEDDINGS (1536-dim) ---
    elif provider == "openai":
        if not Config.OPENAI_API_KEY:
            logger.warning("OpenAI API Key missing, cannot generate embedding.")
            return None
        try:
            client = OpenAI(api_key=Config.OPENAI_API_KEY)
            response = client.embeddings.create(
                input=[text], 
                model=Config.OPENAI_EMBEDDING_MODEL
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error(f"OpenAI embedding error: {e}")
            return None
            
    else:
        logger.error(f"Unknown embedding provider: {provider}")
        return None
