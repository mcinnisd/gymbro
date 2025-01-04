import os
import subprocess

def download_dish_images(dish_list, output_folder):
    # Ensure the output folder exists
    os.makedirs(output_folder, exist_ok=True)
    
    # Base gsutil command template
    base_command = 'gsutil -m cp -r "gs://nutrition5k_dataset/nutrition5k_dataset/imagery/realsense_overhead/{dish}/rgb.png" {output_path}'
    
    for dish in dish_list:
        # Build the command for the specific dish
        dish_output_path = os.path.join(output_folder, f"{dish}.png")
        command = base_command.format(dish=dish, output_path=dish_output_path)
        
        try:
            print(f"Downloading image for dish {dish}...")
            # Run the gsutil command
            subprocess.run(command, shell=True, check=True)
            print(f"Successfully downloaded: {dish_output_path}")
        except subprocess.CalledProcessError as e:
            print(f"Failed to download image for dish {dish}: {e}")

if __name__ == "__main__":
    # List of dish IDs to download
    dishes = [
        "dish_1561662054",
	"dish_1562008979",
	"dish_1566245398",
	"dish_1563476551",
	"dish_1562963704",
	"dish_1564432238",
	"dish_1562691032",
	"dish_1566920365",
	"dish_1564686855",
	"dish_1558637393",
	"dish_1562789268",
	"dish_1563998323",
	"dish_1561492204",
	"dish_1564082178",
	"dish_1558721757",
	"dish_1558720236",
	"dish_1558380557",
	"dish_1558724959",
	"dish_1562618000",
	"dish_1550775363",
	"dish_1564686832",
	"dish_1566938026",
    ]
    
    # Folder to save the downloaded images
    output_folder = "./dish_pics"
    
    # Call the function to download the images
    download_dish_images(dishes, output_folder)
