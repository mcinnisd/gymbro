# app/utils/openai_utils.py

import openai
from flask import current_app
from app.config import Config
# import logging

# Configure logger
# logger = logging.getLogger(__name__)

from openai import OpenAI
client = OpenAI()

# Initialize OpenAI API key
openai.api_key = Config.OPENAI_API_KEY

def generate_chat_response(messages, model="gpt-4o-mini", mode="normal"):
    """
    Generate a chat response from OpenAI based on the provided messages and mode.

    Args:
        messages (list): List of message dictionaries with 'role' and 'content'.
        model (str): OpenAI model to use.
        temperature (float): Sampling temperature.
        mode (str): Prompting mode ('normal' or 'developer').

    Returns:
        str: The generated chatbot response.
    """

    # Validate mode
    if mode not in ["normal", "developer"]:
        # logger.error(f"Invalid mode '{mode}' provided. Defaulting to 'normal'.")
        mode = "normal"

    # Modify messages based on mode
    if mode == "developer":
        # Prepend a developer message to set the assistant's behavior
        developer_prompt = {
            "role": "developer",
            "content": "You are a helpful assistant that provides detailed and accurate answers."
        }
        # Insert at the beginning of the messages list
        messages = [developer_prompt] + messages

    # try:
    response = client.chat.completions.create(
        model=model,
        messages=messages
    )
    bot_reply = response.choices[0].message.content
    # logger.info(f"OpenAI response generated using model '{model}' with mode '{mode}'.")
    return bot_reply
    # except client.error.OpenAIError as e:
    #     logger.error(f"OpenAI API error: {e}")
    #     raise e  # Propagate exception to be handled by the caller




