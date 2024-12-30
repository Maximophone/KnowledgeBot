import imghdr
import base64
import os
from PIL import Image
from io import BytesIO
from typing import Tuple

def encode_image(image_path: str) -> Tuple[str, str]:
    with open(image_path, "rb") as image_file:
        file_content = image_file.read()
        image_type = imghdr.what(None, file_content)
        if image_type is None:
            raise ValueError(f"Unsupported image format for file: {image_path}")
        return base64.b64encode(file_content).decode('utf-8'), f"image/{image_type}"

def validate_image(image_path: str, max_size: int = 20 * 1024 * 1024) -> None:
    if not os.path.isfile(image_path):
        raise FileNotFoundError(f"Image file not found: {image_path}")
    if os.path.getsize(image_path) > max_size:
        raise ValueError(f"Image file too large: {image_path}")
    if imghdr.what(image_path) is None:
        raise ValueError(f"Unsupported image format: {image_path}")

def get_image_dimensions_from_base64(base64_string):
    # Remove the MIME type prefix if present
    if ',' in base64_string:
        base64_string = base64_string.split(',', 1)[1]
    
    # Decode the base64 string
    image_data = base64.b64decode(base64_string)
    
    # Create a file-like object from the decoded data
    image_file = BytesIO(image_data)
    
    # Open the image using PIL
    with Image.open(image_file) as img:
        # Get the dimensions
        width, height = img.size
    
    return width, height 