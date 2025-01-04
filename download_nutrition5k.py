from google.cloud import storage

# Initialize the client
def download_files(bucket_name, prefix, local_directory, file_list):
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    
    for file_name in file_list:
        blob = bucket.blob(f"{prefix}/{file_name}")
        local_path = f"{local_directory}/{file_name}"
        blob.download_to_filename(local_path)
        print(f"Downloaded {file_name} to {local_path}")

# Define parameters
bucket_name = "your-bucket-name"
prefix = "path/to/dataset"  # Adjust based on the folder structure in GCS
local_directory = "./local-dataset"  # Local folder to save files
file_list = ["file1.csv", "file2.csv", "file3.csv"]  # Replace with specific files you want

download_files(bucket_name, prefix, local_directory, file_list)
