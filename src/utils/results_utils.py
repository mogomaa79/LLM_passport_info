import json
import os
import pandas as pd
import gspread
import pickle
import fuzzywuzzy
import traceback
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from collections import Counter

# Define the required OAuth 2.0 scope
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',   # For Google Sheets access
    'https://www.googleapis.com/auth/drive.file'      # For Google Drive file access
]

pd.options.mode.chained_assignment = None

mapper = {
    "Philippines": "PHL", "Ethiopia": "ETH", "Kenya": "KEN", "Nepal": "NPL",
    "Sri Lanka": "LKA", "India": "IND", "Sierra Leone": "SLE", "Uganda": "UGA",
    "Uzbekistan": "UZB", "Bangladesh": "BGD", "Cameroon": "CMR", "Pakistan": "PAK",
    "Brazil": "BRA", "Myanmar": "MMN", "Russia": "RUS", "Spain": "ESP",
    "Hong Kong": "HKG", "Zimbabwe": "ZWE", "Morocco": "MAR", "Indonesia": "IDN",
    "Tanzania": "TZA", "Ivory Coast": "CIV", "Colombia": "COL", "Mexico": "MEX",
    "Nigeria": "NGA", "Tunisia": "TUN", "Thailand": "THA", "Tajikistan": "TJK",
    "Madagascar": "MDG", "Algeria": "DZA", "Georgia": "GEO", "Kyrgyzstan": "KGZ",
    "Kazakhstan": "KAZ", "Azerbaijan": "AZE", "Turkmenistan": "TKM", "Mongolia": "MNG",
    "Armenia": "ARM", "Austria": "AUT", "Belarus": "BLR", "Bulgaria": "BUL",
}

class ResultsAgent:
    def __init__(self, spreadsheet_id: str = "1ljIem8te0tTKrN8N9jOOnPIRh2zMvv2WB_3FBa4ycgA", country: str = "XXX", 
                 credentials_path: str = "credentials.json", excel_paths: list[str] = 
                 ["./static/OCR Extracted Data and User Modifications (feb 1- march 31) .xlsx", 
                  "./static/OCR Extracted Data and User Modifications- April 1 till 28.xlsx",
                  "./static/OCR Extracted Data and User Modifications (1-9-2024 till 14-5-2025).xlsx",
                  "./static/OCR Extracted Data and User Modifications - all 2024.xlsx"],
                 consolidated_file_path: str = "./static/consolidated_data.parquet"):
        
        self.country = country
        self.spreadsheet_id = spreadsheet_id
        self.credentials_path = credentials_path
        self.excel_paths = excel_paths
        self.consolidated_file_path = consolidated_file_path
        
        # Load data efficiently
        self.all_df = self._load_consolidated_data()

    def _load_consolidated_data(self) -> pd.DataFrame:
        """Load data from consolidated file if it exists and is up-to-date, otherwise create it."""
        
        # Check if consolidated file exists and is newer than all Excel files
        if os.path.exists(self.consolidated_file_path):
            consolidated_mtime = os.path.getmtime(self.consolidated_file_path)
            excel_files_newer = False
            
            for excel_path in self.excel_paths:
                if os.path.exists(excel_path):
                    if os.path.getmtime(excel_path) > consolidated_mtime:
                        excel_files_newer = True
                        break
            
            # If consolidated file is up-to-date, load it quickly
            if not excel_files_newer:
                print(f"Loading consolidated data from {self.consolidated_file_path}...")
                df = pd.read_parquet(self.consolidated_file_path)
                print(f"Loaded {len(df)} records from consolidated file.")
                return df
        
        # Otherwise, create consolidated file
        print("Creating consolidated data file...")
        return self._create_consolidated_data()

    def _create_consolidated_data(self) -> pd.DataFrame:
        """Load all Excel files, process them, and save as consolidated Parquet file."""
        all_df = pd.DataFrame()
        
        for excel_path in self.excel_paths:
            if not os.path.exists(excel_path):
                print(f"Warning: File {excel_path} does not exist, skipping...")
                continue
                
            print(f"Loading {excel_path}...")
            try:
                excel_df = pd.read_excel(excel_path, sheet_name="Data")
            except:
                try:
                    excel_df = pd.read_excel(excel_path, sheet_name="Sheet 1")
                except Exception as e:
                    print(f"Error loading {excel_path}: {e}")
                    continue
            
            all_df = pd.concat([all_df, excel_df], ignore_index=True)
        
        # Process the data
        all_df.ffill(inplace=True)
        all_df.drop_duplicates(subset=["Maid’s ID", "Modified Field"], inplace=True)
        
        # Save consolidated file
        os.makedirs(os.path.dirname(self.consolidated_file_path), exist_ok=True)
        all_df.to_parquet(self.consolidated_file_path, index=False)
        print(f"Saved consolidated data to {self.consolidated_file_path} with {len(all_df)} records.")
        
        return all_df

    def refresh_consolidated_data(self):
        """Force refresh of consolidated data by reloading from Excel files."""
        if os.path.exists(self.consolidated_file_path):
            os.remove(self.consolidated_file_path)
        self.all_df = self._create_consolidated_data()

    def edit_agent_value(self, value, field):
        value = str(value).strip().upper()

        if pd.Series(value).str.match(r"^\d{4}-\d{2}-\d{2}$").any() and pd.to_datetime(value, errors='coerce') is not pd.NaT:
            return pd.to_datetime(value).strftime('%d/%m/%Y')

        elif str(field).strip().upper() == "NATIONALITY":
            normalized_value = fuzzywuzzy.process.extractOne(value, mapper.keys())
            return mapper.get(normalized_value[0], "XXX")
        
        elif self.country != "India" and (str(field).strip().upper() == "MOTHER NAME" or str(field).strip().upper() == "FATHER NAME"):
            return ""
        
        elif self.country == "India" and str(field).strip().upper() == "MOTHER NAME":
            return value.split()[0]
        
        elif self.country == "India" and str(field).strip().upper() == "FATHER NAME":
            return value
        
        elif str(field).strip().upper() == "GENDER":
            return value[0]

        return value

    def upload_results(self, csv_file_path: str):
        token_file = 'token.pickle'

        creds = None
        if os.path.exists(token_file):
            with open(token_file, 'rb') as token:
                creds = pickle.load(token)

        # If no valid credentials, perform the OAuth 2.0 flow
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                # Start the OAuth flow to get new credentials
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.credentials_path, SCOPES)
                creds = flow.run_local_server(port=0)

            # Save the credentials for the next time
            with open(token_file, 'wb') as token:
                pickle.dump(creds, token)

        # Now authorize the credentials
        gc = gspread.authorize(creds)

        df = pd.read_csv(csv_file_path)
        merged_df = pd.merge(df, self.all_df, left_on="inputs.image_id", right_on="Maid’s ID", how="left")  

        google_sheet_columns = {
            "Birth Place": "outputs.place of birth",
            "Birthdate": "outputs.birth date",
            "Country of Issue": "outputs.country of issue",
            "First Name": "outputs.name",
            "Gender": "outputs.gender",
            "Last Name": "outputs.surname" if self.country != "India" else "outputs.father name",
            "Middle Name": "outputs.middle name" if self.country != "India" else "outputs.surname",
            "Mother Name": "outputs.mother name",
            "Nationality": "outputs.country",
            "Passport Expiry Date": "outputs.expiry date",
            "Passport Issue Date": "outputs.issue date",
            "Passport Place(EN)": "outputs.place of issue",
            "Passport ID": "outputs.number",
        }

        def get_gemini_value(series):
            maid_id = series["Maid’s ID"]
            field = series["Modified Field"]
            mapped_field = google_sheet_columns.get(field)
            if mapped_field:
                row = df[df["inputs.image_id"] == maid_id]
                if row.empty:
                    return ""
                else:
                    row = row.iloc[0]
                    gemini_value = row.get(mapped_field)
                    if not gemini_value and field == "Passport ID":
                        gemini_value = row.get("outputs.original number")
                    
                    # Handle CertainField objects - extract string value
                    if hasattr(gemini_value, '__str__'):
                        gemini_value = str(gemini_value)
                    
                    # Handle "nan", "NaN", "NAN" strings specifically
                    if isinstance(gemini_value, str) and gemini_value.lower() in ['nan', 'none', 'null', 'n/a', 'na']:
                        gemini_value = ""
                    
                if pd.isna(gemini_value) or gemini_value is None:
                    return ""
                else:
                    return gemini_value
            else:
                return ""
        
        def get_gemini_certainty(series):
            maid_id = series["Maid’s ID"]
            field = series["Modified Field"]
            mapped_field = google_sheet_columns.get(field)
            if mapped_field:
                row = df[df["inputs.image_id"] == maid_id]
                if row.empty:
                    return False
                else:
                    row = row.iloc[0]
                    
                    # Try to get certainty directly from CertainField object first
                    gemini_field = row.get(mapped_field)
                    if hasattr(gemini_field, 'certainty'):
                        return gemini_field.certainty
                    
                    # Fallback: Get certainty from the certainty column
                    certainty_data = row.get('certainty', '{}')
                    if isinstance(certainty_data, str):
                        try:
                            certainty_dict = json.loads(certainty_data)
                            field_name = mapped_field.split('.')[1]
                            return certainty_dict.get(field_name, False)
                        except:
                            return False
                    return False
            else:
                return False
            
        filtered_df = merged_df[['Maid’s ID', 'Modified Field', 'Agent Value', 'OCR Value']]
        filtered_df["Gemini Value"] = filtered_df.apply(get_gemini_value, axis=1)
        filtered_df["Gemini Certainty"] = filtered_df.apply(get_gemini_certainty, axis=1)
        filtered_df["Edited Agent Value"] = filtered_df.apply(lambda row: self.edit_agent_value(row['Agent Value'], row['Modified Field']), axis=1)
        filtered_df["Similarity"] = filtered_df.apply(lambda row: row['Gemini Value'] == row['Edited Agent Value'], axis=1)
        print(filtered_df[filtered_df["Similarity"] == False].shape[0])
        filtered_df = filtered_df[['Maid’s ID', 'Modified Field', 'Edited Agent Value', 'Gemini Value', 'Similarity', 'Gemini Certainty', 'Agent Value', 'OCR Value']]

        filtered_df.dropna(subset=['Maid’s ID'], inplace=True)
        filtered_df['Maid’s ID'] = filtered_df['Maid’s ID'].astype(int)

        headers = filtered_df.columns.tolist()
        data = filtered_df.values.tolist()

        worksheet = gc.open_by_key(self.spreadsheet_id).sheet1
        worksheet.clear()

        data_to_upload = [headers] + [[str(item) for item in row] for row in data]

        worksheet.update('A1', data_to_upload)
        worksheet.freeze(rows=1)

def save_results(results, results_path):
    from src.passport_extraction import CertainField
    
    df = pd.DataFrame(results.to_pandas())
    if 'inputs.multimodal_prompt' not in df.columns:
        df["inputs.image_id"] = df["inputs.inputs"].apply(lambda x: x["image_id"])
        df.drop(columns=['inputs.inputs'], inplace=True)
    else:
        df.drop(columns=['inputs.multimodal_prompt'], inplace=True)

    # Aggregate repetitions to get most frequent values and certainty with CertainField objects
    def aggregate_repetitions(df):
        """Aggregate repetitions by taking most frequent values and creating CertainField objects."""
        aggregated_rows = []
        
        # Group by image_id to process repetitions
        grouped = df.groupby('inputs.image_id')
        
        for image_id, group in grouped:
            # Take the first row as template
            aggregated_row = group.iloc[0].copy()
            
            # Get all output columns
            output_cols = [col for col in group.columns if col.startswith('outputs.')]
            aggregated_outputs = {}
            field_certainties = {}
            
            for col in output_cols:
                field_name = col.split('.')[1]
                # Get all values including None, then clean them
                all_values = group[col].tolist()
                
                # Convert None values to empty strings and clean up
                cleaned_values = []
                for v in all_values:
                    if v is None or pd.isna(v):
                        cleaned_values.append("")
                    else:
                        str_value = str(v)
                        # Handle "nan", "NaN", "NAN" strings specifically
                        if str_value.lower() in ['nan', 'none', 'null', 'n/a', 'na']:
                            cleaned_values.append("")
                        else:
                            cleaned_values.append(str_value)
                
                # Remove empty strings to get meaningful values for frequency counting
                non_empty_values = [v for v in cleaned_values if v.strip()]
                
                if len(non_empty_values) > 1:
                    # Get most frequent value among non-empty values
                    value_counts = Counter(non_empty_values)
                    most_common_value, most_common_count = value_counts.most_common(1)[0]
                    total_non_empty_count = len(non_empty_values)
                    
                    # Certainty is True if all non-empty values agree
                    certainty = (most_common_count == total_non_empty_count)
                    
                    # Create CertainField object
                    certain_field = CertainField(most_common_value, certainty)
                    
                    aggregated_outputs[field_name] = most_common_value
                    field_certainties[field_name] = certainty
                    
                    # Update the aggregated row with CertainField object
                    aggregated_row[col] = certain_field
                elif len(non_empty_values) == 1:
                    # Single non-empty value - create CertainField with no certainty
                    value = non_empty_values[0]
                    certain_field = CertainField(value, False)
                    
                    aggregated_outputs[field_name] = value
                    field_certainties[field_name] = False
                    aggregated_row[col] = certain_field
                else:
                    # No non-empty values or all None - create empty CertainField
                    certain_field = CertainField("", False)
                    
                    aggregated_outputs[field_name] = ""
                    field_certainties[field_name] = False
                    aggregated_row[col] = certain_field
            
            # Create output and certainty JSON strings
            aggregated_row['output'] = json.dumps(aggregated_outputs)
            aggregated_row['certainty'] = json.dumps(field_certainties)
            
            aggregated_rows.append(aggregated_row)
        
        return pd.DataFrame(aggregated_rows)
    
    # Aggregate the repetitions
    aggregated_df = aggregate_repetitions(df)
    
    # Clean up columns
    aggregated_df.rename(columns={'input.image_id': 'image_id'}, inplace=True)
    aggregated_df.to_csv(results_path, index=False) 

def field_match(outputs: dict, reference_outputs: dict) -> float:
    try:
        if "reference_output" in reference_outputs:
            reference_outputs = reference_outputs["reference_output"]
        country = fuzzywuzzy.process.extractOne(reference_outputs["nationality"], mapper.keys())[0]
        convert = lambda value: pd.to_datetime(value).strftime('%d/%m/%Y') if pd.to_datetime(value, errors='coerce') is not pd.NaT else value
        correct = 0
        
        # Use .get() with default values to avoid KeyError issues
        correct += outputs.get("number", "") == reference_outputs.get("passport id", "")
        correct += outputs.get("expiry date", "") == convert(reference_outputs.get("passport expiry date", ""))
        correct += outputs.get("issue date", "") == convert(reference_outputs.get("passport issue date", ""))
        correct += outputs.get("birth date", "") == convert(reference_outputs.get("birthdate", ""))
        correct += outputs.get("place of issue", "") == reference_outputs.get("passport place(en)", "")
        correct += outputs.get("place of birth", "") == reference_outputs.get("birth place", "")
        correct += outputs.get("country of issue", "") == reference_outputs.get("country of issue", "")
        correct += outputs.get("country", "") == mapper.get(country, "XXX")
        correct += outputs.get("gender", "") == reference_outputs.get("gender", [""])[0]
        correct += outputs.get("name", "") == reference_outputs.get("first name", "")
        correct += outputs.get("father name", "") == (reference_outputs.get("last name", "") if country == "India" else "")
        correct += outputs.get("mother name", "") == (reference_outputs.get("mother name", "").split()[0] if country == "India" and reference_outputs.get("mother name", "") else "")
        correct += outputs.get("middle name", "") == ("" if country != "Philippines" else reference_outputs.get("middle name", ""))
        correct += outputs.get("surname", "") == (reference_outputs.get("middle name", "") if country == "India" else reference_outputs.get("last name", ""))

        return correct / 14
    
    except Exception as e:
        print(f"\nAn error occurred during field matching: {e}")
        traceback.print_exc()
        return 0

def full_passport(outputs: dict, reference_outputs: dict) -> bool:
    return field_match(outputs, reference_outputs) == 1