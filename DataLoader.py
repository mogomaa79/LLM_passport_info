import os
import traceback
from helpers import image_to_base64
import pandas as pd

class DataLoader:
    def __init__(self, client, dataset_name, image_path, excel_path, excel_sheet_name="Data"):
        self.client = client
        self.dataset_name = dataset_name
        self.dataset = self.get_dataset()
        self.image_path = image_path
        self.excel_path = excel_path
        self.excel_sheet_name = excel_sheet_name
        self.examples = []
        self.reference_df = None

    def get_dataset(self):
        try:
            dataset = self.client.read_dataset(dataset_name=self.dataset_name)
            print(f"Using existing dataset: {self.dataset_name}")
        except Exception:
            print(f"Creating new dataset: {self.dataset_name}")
            dataset = self.client.create_dataset(
                dataset_name=self.dataset_name,
                description="Dataset containing passport images.",
            )
        return dataset

    def load_reference_data(self):
        try:
            # Read the specified sheet from the Excel file
            all_df = pd.read_excel(self.excel_path, sheet_name=self.excel_sheet_name)
            all_df = all_df.ffill()

            # Ensure required columns exist
            required_cols = ['Maid’s ID', 'Modified Field', 'Agent Value']
            if not all(col in all_df.columns for col in required_cols):
                missing = [col for col in required_cols if col not in all_df.columns]
                print(f"Error: Missing required columns in Excel file: {missing}")
                return 
            
            all_df['Maid’s ID'] = all_df['Maid’s ID'].astype(int).astype(str).str.strip()

            all_df['Agent Value'] = all_df['Agent Value'].fillna('')

            grouped = all_df.groupby('Maid’s ID')

            self.reference_df = grouped

        except FileNotFoundError:
            print(f"Error: Excel file not found at {self.excel_path}")
            self.reference_data = {} # Ensure it's empty if file not found
        except Exception as e:
            print(f"An error occurred loading reference data: {e}")
            traceback.print_exc()
            self.reference_data = {} # Ensure it's empty on error

    def get_reference_data(self, maid_id):
        # Get the group for the given maid_id
        group = self.reference_df.get_group(maid_id)

        # Create a dictionary to store the reference data
        reference_data = {}
        for _, row in group.iterrows():
            modified_field = row['Modified Field']
            agent_value = row['Agent Value']

            reference_data[modified_field.lower()] = str(agent_value)

        return reference_data

    def load_examples(self):
        self.load_reference_data()
        self.examples = [] # Clear previous examples

        try:
            if not os.path.isdir(self.image_path):
                 print(f"Error: Image directory not found at {self.image_path}")
                 return

            image_files = [f for f in os.listdir(self.image_path) if f.lower().endswith((".png", ".jpg", ".jpeg"))]
            
            # Group images by ID (assuming format like '12345.jpg', '12345_2.jpg')
            image_dict = {}
            for img_filename in image_files:
                image_id = os.path.splitext(img_filename)[0].split('_')[0] 
                image_id = image_id.strip()

                if image_id not in image_dict:
                    image_dict[image_id] = []
                image_dict[image_id].append(img_filename)
            
            for img_id in image_dict:
                 image_dict[img_id].sort() # Simple sort often works for _1, _2

            for image_id, img_filenames in image_dict.items():
                reference_output_dict = self.get_reference_data(image_id)

                # Prepare multimodal content for the image(s)
                multimodal_content = []
                has_valid_image = False
                for img_filename in img_filenames:
                    image_full_path = os.path.join(self.image_path, img_filename)
                    try:
                        image_data_uri = image_to_base64(image_full_path)
                        if not image_data_uri:
                            print(f"Skipping image due to processing error: {image_full_path}")
                            continue

                        multimodal_content.append(
                            {
                                "type": "image_url",
                                "image_url": {"url": image_data_uri},
                            },
                        )
                        has_valid_image = True
                    except FileNotFoundError:
                        print(f"Warning: Image file not found: {image_full_path}")
                    except Exception as e:
                         print(f"Warning: Error processing image {image_full_path}: {e}")

                if not has_valid_image:
                     print(f"Skipping example for ID {image_id} as no valid images could be processed.")
                     continue

                # Define inputs for LangSmith example
                example_inputs = {
                    "multimodal_prompt": multimodal_content,
                    "image_id": image_id 
                }

                example_outputs = {"reference_output": reference_output_dict} if reference_output_dict is not None else None
                
                self.examples.append(
                    {
                        "inputs": example_inputs,
                        "outputs": example_outputs,
                    }
                )

            print(f"Prepared {len(self.examples)} examples.")

        except FileNotFoundError:
             print(f"Error: Image directory not found at {self.image_path}")
        except Exception as e:
            print(f"An error occurred loading examples: {e}")
            traceback.print_exc()


    def upload_to_dataset(self):
        if not self.examples:
            print("No examples loaded or prepared. Skipping data upload.")
            return

        print(f"Uploading {len(self.examples)} examples to dataset '{self.dataset_name}'...")
        try:
            # Prepare inputs and outputs lists
            inputs = [ex["inputs"] for ex in self.examples]
            outputs = [ex["outputs"] for ex in self.examples] 
            chunk_size = 24 # Adjust chunk size based on payload limits and performance
            num_chunks = (len(self.examples) + chunk_size - 1) // chunk_size

            for i in range(0, len(self.examples), chunk_size):
                chunk_num = (i // chunk_size) + 1
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


    def run(self):
        self.load_examples() # This now includes loading reference data
        self.upload_to_dataset()