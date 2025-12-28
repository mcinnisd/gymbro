from app import create_app
from app.utils.llm_utils import generate_chat_response
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def verify_llm():
    app = create_app()
    with app.app_context():
        logger.info("Testing LLM Generation...")
        messages = [{"role": "user", "content": "Hello, are you ready to coach me?"}]
        
        try:
            response = generate_chat_response(messages, mode="coach")
            logger.info(f"LLM Response: {response}")
            
            if "Error" in response:
                logger.error("LLM Verification FAILED.")
            else:
                logger.info("LLM Verification SUCCESS.")
        except Exception as e:
            logger.error(f"LLM Verification Exception: {e}")

if __name__ == "__main__":
    verify_llm()
