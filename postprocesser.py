#!/usr/bin/env python3

import pandas as pd
import json
import os
import traceback

# Import postprocessing functions
from src.utils.passport_processing import postprocess
from src.utils.results_utils import upload_results

def process_file(file_path):
    """Apply postprocessing to all rows in the file."""
    print(f"\nProcessing file: {os.path.basename(file_path)}")
    
    # Extract country/dataset name from filename
    project_name = os.path.basename(file_path).replace('_results.csv', '')
    country = project_name.split(' - ')[0].strip()
    print(f"Detected country/dataset: {country}")
    
    # Read the CSV file
    df = pd.read_csv(file_path)
    print(f"Read {len(df)} rows from {os.path.basename(file_path)}")
    
    # Apply postprocessing to each row
    processed_rows = []
    
    for i, (_, row) in enumerate(df.iterrows()):
        try:
            # Extract output data
            if 'output' in row:
                output_dict = json.loads(row['output'])
            else:
                # Create output dict from output.* columns
                output_dict = {}
                for col in row.index:
                    if col.startswith('outputs.'):
                        field_name = col.replace('outputs.', '')
                        output_dict[field_name] = row[col]
            
            # Apply postprocessing
            processed = postprocess(output_dict, country)
            
            # Create new row with processed values
            new_row = row.copy()
            
            # Update outputs with processed values
            for key, value in processed.items():
                col_name = f'outputs.{key}'
                new_row[col_name] = value
            
            processed_rows.append(new_row)
            
            # Show progress
            if (i + 1) % 10 == 0 or i == len(df) - 1:
                print(f"Processed {i + 1}/{len(df)} rows", end='\r')
        
        except Exception as e:
            print(f"\nError processing row {i}: {e}")
            processed_rows.append(row)  # Keep original row on error
    
    print("\nPostprocessing completed")
    
    # Create new dataframe with processed data
    processed_df = pd.DataFrame(processed_rows)
    
    # Update the output column with processed values
    processed_df['output'] = processed_df.apply(
        lambda row: json.dumps({key.split('.')[1]: row[key] for key in row.index if key.startswith("outputs.")}), 
        axis=1
    )
    
    # Save the processed results
    results_dir = "processed_results/"
    output_file = f"{results_dir}{project_name}_processed_results.csv"
    processed_df.to_csv(output_file, index=False)
    
    return output_file, country

def upload_to_sheets(output_file, country):
    """Upload processed results to Google Sheets."""
    try:
        spreadsheet_id = "1ljIem8te0tTKrN8N9jOOnPIRh2zMvv2WB_3FBa4ycgA"
        credentials_path = "credentials.json"
        
        upload_results(output_file, spreadsheet_id, credentials_path, country)

    except Exception as e:
        print(f"Error during upload: {e}")
        traceback.print_exc()

def main():
    file_path = "results/India - gemini-2.5-pro-preview-05-06 - 848_results.csv"
    
    output_file, country = process_file(file_path)
    
    upload_to_sheets(output_file, country)

    print("\nUpload completed.")

if __name__ == "__main__":
    main() 