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

MODELS = [
	# "gpt-4-turbo",
	"gpt-4o-mini",
	"gpt-4o",
]

PROMPTS = [
    (
        "You are a professional at analyzing food and predicting the total calories, fat, carbohydrates, and protein within the meal. "
        "Use your superior skills to accurately predict what is contained in the meal in the following image. "
        "Please provide your response in a structured JSON format containing only the following fields without any units: calories, fat, "
        "carbohydrates, and protein. Do not include any additional text, explanations, or formatting."
    ),
]

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

def get_openai_prediction(encoded_image, model_name, prompt):
	"""
	Send the encoded image to OpenAI and get macro predictions.
	"""
	# prompt = (
	# 	"You are provided with an image of a meal. Your task is to analyze the image and estimate the total "
	# 	"calories along with the macronutrients: fat, carbohydrates, and protein. Please provide your response "
	# 	"in a structured JSON format containing only the following fields without any units: calories, fat, "
	# 	"carbohydrates, and protein. Do not include any additional text, explanations, or formatting."
	# )
	
	try:
		response = client.chat.completions.create(
			model=model_name,
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

# import re
# import json

# def clean_response(response_text):
#     """
#     Extract JSON content from a mixed response by identifying JSON code blocks or inline JSON.
    
#     Parameters:
#         response_text (str): The raw response text from the model.
    
#     Returns:
#         str: Cleaned JSON string if found, else the original response.
#     """
#     # Define a regex pattern to find ```json ... ``` blocks
#     json_code_block_pattern = r'```json\s*\n(.*?)\n```'
    
#     # Search for the JSON code block
#     match = re.search(json_code_block_pattern, response_text, re.DOTALL | re.IGNORECASE)
#     if match:
#         json_str = match.group(1).strip()
#         # Validate and format the JSON
#         try:
#             parsed_json = json.loads(json_str)
#             return json.dumps(parsed_json, indent=2)
#         except json.JSONDecodeError:
#             pass  # If JSON is invalid, proceed to next step
    
#     # If no code block is found, attempt to find inline JSON
#     inline_json_pattern = r'(\{.*?\})'
#     matches = re.findall(inline_json_pattern, response_text, re.DOTALL)
#     for json_candidate in matches:
#         try:
#             parsed_json = json.loads(json_candidate)
#             return json.dumps(parsed_json, indent=2)
#         except json.JSONDecodeError:
#             continue  # Try next match if current is invalid
    
#     # If no JSON is found, return the original response or handle as needed
#     return response_text

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

def main():
    """
    Main function to process all images, get predictions from multiple models and detail levels,
    and calculate average differences between predictions and actual data.
    """
    # Initialize aggregation dictionary
    aggregation = {
        model: {
            prompt: {
                "calories_diff": [],
                "fat_diff": [],
                "carbohydrates_diff": [],
                "protein_diff": []
            } for prompt in PROMPTS
        } for model in MODELS
    }
    total_images = 0

    # Iterate through all images in the directory
    for image_name in os.listdir(DISH_PICS_DIR):
        if not image_name.lower().endswith(('.png', '.jpg', '.jpeg', '.gif')):
            continue  # Skip non-image files

        image_path = os.path.join(DISH_PICS_DIR, image_name)
        print(f"\nProcessing image: {image_name}")
        total_images += 1
        
        # Optional: Limit the number of images to process
        # if total_images > 6:
        #     break

        # Encode image without resizing
        encoded_image = encode_image(image_path)
        if not encoded_image:
            print("Failed to encode the image.")
            continue

        # Get actual nutrition data
        actual_nutrition = get_nutrition_from_csv(image_name, CSV_FILE_PATH)
        if not actual_nutrition:
            print("Failed to retrieve actual nutrition data.")
            continue

        # Iterate through each model and detail level
        for model in MODELS:
            for i, prompt in enumerate(PROMPTS):
                print(f"\nModel: {model} | Prompt: {i}")
                # Get OpenAI prediction
                prediction_text = get_openai_prediction(encoded_image, model_name=model, prompt=prompt)
                if not prediction_text:
                    print("Failed to get prediction from OpenAI.")
                    continue

                print("OpenAI Prediction:")
                print(prediction_text)

                # Parse prediction
                prediction_data = parse_openai_response(prediction_text)
                if not prediction_data:
                    print("Failed to parse prediction data.")
                    continue

                # Calculate differences
                calories_diff = abs(prediction_data["calories"] - actual_nutrition["total_calories"])
                fat_diff = abs(prediction_data["fat"] - actual_nutrition["total_fat"])
                carbohydrates_diff = abs(prediction_data["carbohydrates"] - actual_nutrition["total_carbohydrates"])
                protein_diff = abs(prediction_data["protein"] - actual_nutrition["total_protein"])

                # Append differences to aggregation
                aggregation[model][prompt]["calories_diff"].append(calories_diff)
                aggregation[model][prompt]["fat_diff"].append(fat_diff)
                aggregation[model][prompt]["carbohydrates_diff"].append(carbohydrates_diff)
                aggregation[model][prompt]["protein_diff"].append(protein_diff)

                print("\nComparison:")
                print(f"{'Metric':<15}{'Predicted':<15}{'Actual':<15}{'Difference':<15}")
                print("-" * 60)
                metrics = ['calories', 'protein', 'carbohydrates', 'fat']
                for metric in metrics:
                    predicted = prediction_data.get(metric, 'N/A')
                    actual = actual_nutrition.get(f"total_{metric}", 'N/A')
                    difference = locals()[f"{metric}_diff"]
                    print(f"{metric.capitalize():<15}{predicted:<15}{actual:<15}{difference:<15}")

    # Calculate and display average differences
    print("\n--- Average Differences Across All Images ---")
    print(f"Total Images Processed: {total_images}\n")
    for model in MODELS:
        for i, prompt in enumerate(PROMPTS):
            num_predictions = len(aggregation[model][prompt]["calories_diff"])
            if num_predictions == 0:
                print(f"Model: {model} | Prompt: {i} - No data to display.")
                continue

            avg_calories_diff = sum(aggregation[model][prompt]["calories_diff"]) / num_predictions
            avg_fat_diff = sum(aggregation[model][prompt]["fat_diff"]) / num_predictions
            avg_carbohydrates_diff = sum(aggregation[model][prompt]["carbohydrates_diff"]) / num_predictions
            avg_protein_diff = sum(aggregation[model][prompt]["protein_diff"]) / num_predictions

            print(f"Model: {model} | Prompt: {i}")
            print(f"  Average Calories Difference: {avg_calories_diff:.2f}")
            print(f"  Average Fat Difference: {avg_fat_diff:.2f}g")
            print(f"  Average Carbohydrates Difference: {avg_carbohydrates_diff:.2f}g")
            print(f"  Average Protein Difference: {avg_protein_diff:.2f}g\n")

if __name__ == "__main__":
	main()