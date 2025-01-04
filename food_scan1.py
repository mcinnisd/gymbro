import os
import base64
import pandas as pd
from dotenv import load_dotenv
from openai import OpenAI  # Ensure you have the OpenAI Python package installed
import json
from dish_pics.get_info import get_nutrition_from_csv

# Load environment variables
load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DISH_PICS_DIR = "dish_pics/"
CSV_FILE_PATH = "dish_pics/dish_metadata_cafe1.csv"

# Initialize OpenAI client
client = OpenAI(api_key=OPENAI_API_KEY)

def encode_image(image_path):
	"""
	Encode an image file to a base64 string.
	"""
	if not os.path.exists(image_path):
		print(f"Image file does not exist: {image_path}")
		return None
	try:
		with open(image_path, "rb") as image_file:
			return base64.b64encode(image_file.read()).decode("utf-8")
	except Exception as e:
		print(f"Error encoding image: {e}")
		return None

def get_openai_prediction(encoded_image):
	"""
	Send the encoded image to OpenAI and get macro predictions.
	"""
	prompt = (
        "You are a professional at analyzing food and predicting the total calories, fat, carbohydrates, and protein within the meal. "
        "Use your superior skills to accurately predict what is contained in the meal in the following image. "
        "Please provide your response in a structured JSON format containing only the following fields without any units: calories, fat, "
        "carbohydrates, and protein. Do not include any additional text, explanations, or formatting."
    )
	
	try:
		response = client.chat.completions.create(
			model="gpt-4o-mini",
			messages=[
				{
					"role": "user",
					"content": [
						{"type": "text", "text": prompt},
						{
							"type": "image_url",
							"image_url": {
								"url": f"data:image/jpeg;base64,{encoded_image}",
								"detail": "low"
							},
						},
					],
				}
			],
			max_tokens=300,
		)
		return response.choices[0].message.content
	except Exception as e:
		print(f"Error calling OpenAI API: {e}")
		return None

def clean_response(response_text):
	"""
	Clean the response text to extract JSON by removing Markdown code block delimiters.
	"""
	# Check if the response starts with ```json and ends with ```
	if response_text.startswith("```") and response_text.endswith("```"):
		# Split the response into lines
		lines = response_text.split('\n')
		# Remove the first and last lines (code block delimiters)
		if len(lines) >= 3:
			return '\n'.join(lines[1:-1])
	return response_text

def parse_openai_response(response_text):
	"""
	Parse the OpenAI JSON response to extract macro estimates.
	Handles variations in key names by normalizing them.
	"""
	try:
		# Clean the response to remove code block delimiters if present
		cleaned_response = clean_response(response_text)
		
		# Attempt to parse the cleaned response as JSON
		data = json.loads(cleaned_response)
		
		# Normalize keys by removing any units or extra characters
		normalized_data = {}
		for key, value in data.items():
			# Remove any content within parentheses and strip whitespace
			normalized_key = key.split('(')[0].strip().lower()
			normalized_data[normalized_key] = value
		
		# Extract required fields
		calories = normalized_data.get("calories")
		fat = normalized_data.get("fat")
		carbohydrates = normalized_data.get("carbohydrates")
		protein = normalized_data.get("protein")
		
		# Validate the presence of all required fields
		if None in (calories, fat, carbohydrates, protein):
			print("Missing one or more required fields in the response.")
			return None
		
		return {
			"calories": calories,
			"fat": fat,
			"carbohydrates": carbohydrates,
			"protein": protein
		}
	except json.JSONDecodeError:
		print("Failed to parse response as JSON.")
		return None
	except Exception as e:
		print(f"Error parsing OpenAI response: {e}")
		return None

