import google.generativeai as genai
from openai import OpenAI
from flask import current_app
from app.config import Config
import logging

# Configure logger
logger = logging.getLogger(__name__)

# Initialize Gemini (if key present)
if Config.GEMINI_API_KEY:
    genai.configure(api_key=Config.GEMINI_API_KEY)

def generate_chat_response(messages, model_name="gemini-2.0-flash-exp", mode="normal", system_prompt=None, provider=None, context=None, stream=False):
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

    Returns:
        str or generator: The generated chatbot response.
    """
    if not provider:
        provider = Config.LLM_PROVIDER
    
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

Remember: Your credibility depends on accuracy. Never invent numbers."""
        else:
            system_instruction = "You are a helpful assistant."

    # Inject context into system prompt if provided
    if context and context.strip():
        system_instruction = f"{system_instruction}\n\n{context}"
        logger.debug(f"Context injected into system prompt ({len(context)} chars)")

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
                def generate():
                    for chunk in completion:
                        if chunk.choices[0].delta.content:
                            yield chunk.choices[0].delta.content
                return generate()
            else:
                return completion.choices[0].message.content

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
                stream=stream
            )
            
            if stream:
                def generate():
                    for chunk in completion:
                        if chunk.choices[0].delta.content:
                            yield chunk.choices[0].delta.content
                return generate()
            else:
                return completion.choices[0].message.content
                
        except Exception as e:
            logger.error(f"OpenAI API Error: {e}")
            return f"Error communicating with OpenAI Coach: {e}"

    # --- GEMINI ---
    elif provider == "gemini":
        if not Config.GEMINI_API_KEY:
            return "Gemini API Key missing."

        try:
            model = genai.GenerativeModel(
                model_name=model_name,
                system_instruction=system_instruction
            )

            gemini_history = []
            for msg in messages:
                if msg["role"] == "system":
                    continue
                gemini_role = "user" if msg["role"] == "user" else "model"
                gemini_history.append({"role": gemini_role, "parts": [msg["content"]]})

            if not gemini_history:
                return "Error: No messages provided."

            last_message = gemini_history[-1]
            history_to_send = gemini_history[:-1]
            
            if last_message["role"] != "user":
                logger.warning("Last message in history is not from user.")
            
            chat = model.start_chat(history=history_to_send)
            response = chat.send_message(last_message["parts"][0], stream=stream)
            
            if stream:
                def generate():
                    for chunk in response:
                        if chunk.text:
                            yield chunk.text
                return generate()
            else:
                return response.text

        except Exception as e:
            logger.error(f"Gemini API error: {e}")
            return f"Error communicating with Gemini Coach: {e}"

    else:
        return f"Unknown LLM Provider: {provider}"
