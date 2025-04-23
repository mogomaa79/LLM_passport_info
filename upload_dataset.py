from langsmith import Client
from pathlib import Path
import mimetypes
import base64

API_KEY = "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"  # Replace with your actual API key
ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg"}

client = Client(api_key=API_KEY)

# It's often safer to create the dataset if it doesn't exist
# or handle the case where it might not be found by name alone
# If you are SURE it exists and want to read it:
try:
    dataset = client.read_dataset(dataset_name="Passport Images")
except Exception as e:
    print(f"Dataset 'Passport Images' not found or error reading: {e}")
    print("Please ensure the dataset exists in LangSmith.")
    # You might want to exit or create the dataset here if needed
    exit() # Or handle dataset creation

images_dir = Path("images")

# Ensure the images directory exists and contains files before proceeding
if not images_dir.exists() or not any(images_dir.iterdir()):
    print(f"Error: Directory '{images_dir}' not found or is empty.")
    print("Please create the 'images' directory and place your image files inside.")
    exit()

examples = []

# Process both .png and .jpg files
for extension in ALLOWED_EXTENSIONS:
    for img_path in images_dir.glob(f"*{extension}"): # Use f-string for clarity
        try:
            # Read image file as binary
            with open(img_path, "rb") as image_file:
                img_bytes = image_file.read()

            # Base64 encode the image bytes
            base64_image_string = base64.b64encode(img_bytes).decode('utf-8')

            # Guess mime type
            mime_type, _ = mimetypes.guess_type(img_path)
            if not mime_type:
                 print(f"Warning: Could not determine mime type for {img_path}. Skipping.")
                 continue # Skip if mime type cannot be determined

            # Construct the input structure for multimodal models
            # The key name ("image_data" here) must match the input key expected by your LangChain/chain
            # This format represents an image using its bytes
            image_input_structure = {
                "type": "image_bytes",
                "image_bytes": {
                    "data": base64_image_string,
                    "mime_type": mime_type
                }
            }

            # Multimodal inputs often need to be in a list, especially if combining text and images
            # Let's put it in a list here. Adapt this if your chain expects a different structure.
            # Example: If your chain expects an input key 'input' which is a list of text/image objects:
            # inputs_payload = {"input": [image_input_structure]}
            # If your chain expects an input key 'image_input' which is JUST the image object:
            # inputs_payload = {"image_input": image_input_structure}

            # **Important:** Replace "image_input_key" with the actual name of the input key
            # your Gemini chain/application expects for the image data.
            # A common pattern in LangChain for models like Gemini is expecting a list of content objects
            # under a main key like 'input', 'messages', or a custom key.
            # Let's assume your chain expects a single input key, say "multimodal_prompt", which is a list of content parts:
            inputs_payload = {
                 "multimodal_prompt": [ # <-- **Change "multimodal_prompt" to your chain's actual input key name**
                      {
                          "type": "text",
                          "text": "Extract the following information from this passport image: Full Name, Passport Number, Date of Birth, Expiry Date."
                      },
                      image_input_structure # Add the image part
                 ]
                 # Or, if your chain expects separate keys for text and image:
                 # "text_prompt": "...",
                 # "image_data": image_input_structure # <-- Another possible structure
            }
            # **You MUST adjust `inputs_payload` to match how your specific LangChain/application expects the input.**
            # Check your chain's `.invoke({"key": value})` structure or how it's defined.

            example = {
                "inputs": inputs_payload,
                "outputs": {},  # Optional: can be left empty or include expected outputs (the extracted text)
                # Remove attachments as the image is now in inputs
                # "attachments": {}
            }
            examples.append(example)

        except Exception as e:
            print(f"Error processing {img_path}: {e}")
            # Decide if you want to skip or stop on error

if not examples:
    print("No valid images found or processed. No examples to upload.")
else:
    print(f"Uploading {len(examples)} examples to dataset '{dataset.name}'...")
    client.create_examples(
        dataset_id=dataset.id,
        examples=examples,
    )
    print("Examples uploaded successfully.")