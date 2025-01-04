import os
import csv

def get_nutrition_from_csv(image_name, csv_path):
    """
    Given the name of an image and a CSV file with nutrition data,
    return the total calories, fat, carbs, and protein for the dish.
    
    Parameters:
        image_name (str): The name of the image file (e.g., 'dish_0000000001.png').
        csv_path (str): Path to the CSV file containing nutrition data.
    
    Returns:
        dict: A dictionary with total_calories, total_fat, total_carb, and total_protein.
              Returns None if the dish_id is not found.
    """
    # Extract dish_id from the image name
    dish_id = image_name.replace(".png", "")
    
    try:
        with open(csv_path, mode='r') as file:
            csv_reader = csv.reader(file)
            
            # Loop through each row in the CSV
            for row in csv_reader:
                if len(row) == 0:
                    continue  # Skip empty rows
                
                # Check if the first column matches the dish_id
                if row[0] == dish_id:
                    # Extract relevant nutrition data
                    try:
                        nutrition = {
                            "total_calories": float(row[1]),
                            "total_fat": float(row[3]),
                            "total_carbohydrates": float(row[4]),
                            "total_protein": float(row[5]),
                        }
                        return nutrition
                    except (IndexError, ValueError) as e:
                        print(f"Error extracting data for dish ID {dish_id}: {e}")
                        return None
            
            print(f"Dish ID {dish_id} not found in the CSV.")
            return None

    except Exception as e:
        print(f"Error reading CSV file: {e}")
        return None

# Main program
if __name__ == "__main__":
    # CSV file path
    csv_file_path = "dish_metadata_cafe1.csv"
    
    # Get all PNG files in the current directory
    image_files = [f for f in os.listdir('.') if f.endswith('.png')]
    
    # Loop through the images and get nutrition data
    for image_name in image_files:
        nutrition_data = get_nutrition_from_csv(image_name, csv_file_path)
        if nutrition_data:
            print(f"Nutrition data for {image_name}: {nutrition_data}")