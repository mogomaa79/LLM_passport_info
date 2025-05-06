import base64
from io import BytesIO
from PIL import Image

def image_to_base64(image_path, max_size=(1024, 1024), quality=90):
    """Loads an image, compresses it in memory, resizes it if needed, and converts it to a base64 data URI."""
    try:
        with Image.open(image_path) as img:
            # Resize the image if it's larger than the max_size
            img.thumbnail(max_size)

            # Compress the image in memory (without saving to disk)
            buffered = BytesIO()

            # If the image is in a format that can support transparency, handle it
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB") 
            img.save(buffered, format="JPEG", quality=quality)  # Adjust quality for compression
            img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
            return f"data:image/jpeg;base64,{img_str}"
    except FileNotFoundError:
        print(f"ERROR: Image file not found at '{image_path}'.")
        return None
    except Exception as e:
        print(f"Error processing image {image_path}: {e}")
        return None 