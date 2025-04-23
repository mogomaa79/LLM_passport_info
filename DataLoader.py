import os
import traceback
from helpers import image_to_base64, PassportExtraction
from langchain_core.output_parsers import JsonOutputParser

class DataLoader:
    def __init__(self, client, dataset_name, prompt_path, image_path):
        self.client = client
        self.dataset_name = dataset_name
        self.json_parser = None # Will be set in load_prompt
        self.dataset = self.get_dataset()
        self.prompt_path = prompt_path
        self.prompt = self.load_prompt()
        self.image_path = image_path
        self.examples = [] # List to hold example data before upload

    def get_dataset(self):
        try:
            dataset = self.client.read_dataset(dataset_name=self.dataset_name)
            print(f"Using existing dataset: {self.dataset_name}")
        except Exception:
            print(f"Creating new dataset: {self.dataset_name}")
            dataset = self.client.create_dataset(
                dataset_name=self.dataset_name,
                description="Dataset containing passport images and extraction prompts for Gemini evaluation.",
            )
        return dataset
    
    def load_prompt(self):
        try:
            with open(self.prompt_path, "r", encoding="utf-8") as f:
                base_prompt_text = f.read()

                # Initialize json_parser here
                self.json_parser = JsonOutputParser(pydantic_object=PassportExtraction)
                format_instructions = self.json_parser.get_format_instructions()

                prompt_text = f"{base_prompt_text}\n\n{format_instructions}"
            return prompt_text
        except FileNotFoundError:
            print(f"Error: Prompt file not found at {self.prompt_path}")
            raise
        except Exception as e:
            print(f"Error loading prompt file: {e}")
            raise

    def load_examples(self):
        """
        Loads image examples and prepares multimodal prompts, only passing the image for input.
        The prompt will be embedded by Langchain.
        """
        self.examples = []  # Clear previous examples if run multiple times

        try:
            if not os.path.isdir(self.image_path):
                print(f"Error: Image directory not found at {self.image_path}")
                return

            image_files = [f for f in os.listdir(self.image_path) if f.lower().endswith((".png", ".jpg", ".jpeg"))]
            print(f"Preparing {len(image_files)} examples from {self.image_path}...")

            for img_filename in image_files:
                image_full_path = os.path.join(self.image_path, img_filename)
                reference_output = None  # Assuming no reference output for now

                filename_without_extension, _ = os.path.splitext(img_filename)
                example_id = filename_without_extension 

                image_data_uri = image_to_base64(image_full_path)
                if not image_data_uri:
                    print(f"Skipping example due to image processing error for: {image_full_path}")
                    continue

                example_inputs = {
                    "image_data_uri": image_data_uri,
                    "image_id": example_id
                }

                self.examples.append(
                    {
                        "inputs": example_inputs,
                        "outputs": {"expected_json": reference_output} if reference_output is not None else None,
                    }
                )

            print(f"Prepared {len(self.examples)} examples.")
        except FileNotFoundError:
            print(f"Error: Image directory not found at {self.image_path}")
        except Exception as e:
            print(f"An error occurred loading examples: {e}")
            traceback.print_exc()

    def upload_to_dataset(self):
        """
        Uploads the prepared examples to the LangSmith dataset, including
        the 'id' (filename without extension) as metadata.
        """
        if self.examples:
            print(f"Uploading {len(self.examples)} examples to dataset '{self.dataset_name}'...")
            try:
                # Prepare inputs and outputs lists
                inputs = [ex["inputs"] for ex in self.examples]
                outputs = [ex["outputs"] for ex in self.examples]

                chunk_size = 4
                for i in range(0, len(self.examples), chunk_size):
                    chunk_inputs = inputs[i:i + chunk_size]
                    chunk_outputs = outputs[i:i + chunk_size]

                    # Upload the current chunk
                    self.client.create_examples(
                        inputs=chunk_inputs,
                        outputs=chunk_outputs,
                        dataset_id=self.dataset.id,
                    )

                print(f"Successfully uploaded all {len(self.examples)} examples to dataset '{self.dataset_name}'.")

            except Exception as e:
                print(f"Error uploading examples to dataset: {e}")
                traceback.print_exc()
        else:
            print("No examples loaded or prepared. Skipping data upload.")



    def run(self):
        """
        Loads examples and uploads them to the dataset.
        """
        self.load_examples() # Load examples first
        self.upload_to_dataset() # Then upload them
        print("Data loading and upload process completed.")