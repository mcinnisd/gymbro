import logging
import os
from app.config import Config

logger = logging.getLogger(__name__)

def upload_file_to_gcs(file_bytes: bytes, filename: str, content_type: str = 'application/octet-stream') -> str:
    """
    Upload file bytes to Google Cloud Storage (GCS) bucket.
    Falls back to local file storage URL if GCS is not enabled.
    """
    bucket_name = getattr(Config, 'GCS_BUCKET_NAME', 'gymbro-health-uploads')
    
    if bucket_name:
        try:
            from google.cloud import storage
            storage_client = storage.Client(
                project=getattr(Config, 'GOOGLE_CLOUD_PROJECT', 'gymbro-499418')
            )
            bucket = storage_client.bucket(bucket_name)
            blob = bucket.blob(filename)
            blob.upload_from_string(file_bytes, content_type=content_type)
            
            gcs_url = f"https://storage.googleapis.com/{bucket_name}/{filename}"
            logger.info(f"Successfully uploaded {filename} to GCS: {gcs_url}")
            return gcs_url
        except Exception as e:
            logger.warning(f"GCS upload failed ({e}), using local upload path.")

    # Local fallback
    upload_dir = os.path.join(os.getcwd(), 'uploads')
    os.makedirs(upload_dir, exist_ok=True)
    local_path = os.path.join(upload_dir, filename)
    
    with open(local_path, 'wb') as f:
        f.write(file_bytes)
        
    return f"/storage/local/{filename}"
