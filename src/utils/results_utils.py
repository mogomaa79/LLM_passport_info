import json
import os
import pandas as pd
import gspread
import pickle
import fuzzywuzzy
import traceback
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

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
                  "./static/OCR Extracted Data and User Modifications - all 2024.xlsx"]):
        
        self.country = country
        self.spreadsheet_id = spreadsheet_id
        self.credentials_path = credentials_path
        self.all_df = pd.DataFrame()
        for excel_path in excel_paths:
            try:
                excel_df = pd.read_excel(excel_path, sheet_name="Data")
            except:
                excel_df = pd.read_excel(excel_path, sheet_name="Sheet 1")
            self.all_df = pd.concat([self.all_df, excel_df])
        self.all_df.ffill(inplace=True)
        self.all_df.drop_duplicates(subset=["Maid’s ID", "Modified Field"], inplace=True)

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
                if pd.isna(gemini_value):
                    return ""
                else:
                    return gemini_value
            else:
                return ""
            
        filtered_df = merged_df[['Maid’s ID', 'Modified Field', 'Agent Value', 'OCR Value']]
        filtered_df["Gemini Value"] = filtered_df.apply(get_gemini_value, axis=1)
        filtered_df["Edited Agent Value"] = filtered_df.apply(lambda row: self.edit_agent_value(row['Agent Value'], row['Modified Field']), axis=1)
        filtered_df["Similarity"] = filtered_df.apply(lambda row: row['Gemini Value'] == row['Edited Agent Value'], axis=1)
        print(filtered_df[filtered_df["Similarity"] == False].shape[0])
        filtered_df = filtered_df[['Maid’s ID', 'Modified Field', 'Edited Agent Value', 'Gemini Value', 'Similarity', 'Agent Value', 'OCR Value']]
        filtered_df.dropna(subset=['Maid’s ID'], inplace=True)
        print(filtered_df["Maid’s ID"].unique())
        filtered_df['Maid’s ID'] = filtered_df['Maid’s ID'].astype(int)

        headers = filtered_df.columns.tolist()
        data = filtered_df.values.tolist()

        worksheet = gc.open_by_key(self.spreadsheet_id).sheet1
        worksheet.clear()

        data_to_upload = [headers] + [[str(item) for item in row] for row in data]

        worksheet.update('A1', data_to_upload)
        worksheet.freeze(rows=1)

def save_results(results, results_path):
    df = pd.DataFrame(results.to_pandas())
    if 'inputs.multimodal_prompt' not in df.columns:
        df["inputs.image_id"] = df["inputs.inputs"].apply(lambda x: x["image_id"])
        df.drop(columns=['inputs.inputs'], inplace=True)
    else:
        df.drop(columns=['inputs.multimodal_prompt'], inplace=True)

    df['output'] = df.apply(lambda row: json.dumps({key.split('.')[1]: row[key] for key in df.columns if key.startswith("output")}), axis=1)
    df.rename(columns={'input.image_id': 'image_id'}, inplace=True)
    df.to_csv(results_path, index=False) 

def field_match(outputs: dict, reference_outputs: dict) -> float:
    try:
        if "reference_output" in reference_outputs:
            reference_outputs = reference_outputs["reference_output"]
        country = fuzzywuzzy.process.extractOne(reference_outputs["nationality"], mapper.keys())[0]
        convert = lambda value: pd.to_datetime(value).strftime('%d/%m/%Y') if pd.to_datetime(value, errors='coerce') is not pd.NaT else value
        correct = 0
        correct += outputs["number"] == reference_outputs["passport id"]
        correct += outputs["expiry date"] == convert(reference_outputs["passport expiry date"])
        correct += outputs["issue date"] == convert(reference_outputs["passport issue date"])
        correct += outputs["birth date"] == convert(reference_outputs["birthdate"])
        correct += outputs["place of issue"] == reference_outputs["passport place(en)"]
        correct += outputs["place of birth"] == reference_outputs["birth place"]
        correct += outputs["country of issue"] == reference_outputs["country of issue"]
        correct += outputs["country"] == mapper.get(country, "XXX")
        correct += outputs["gender"] == reference_outputs["gender"][0]
        correct += outputs["name"] == reference_outputs["first name"]
        correct += outputs["father name"] == (reference_outputs["last name"] if country == "India" else "")
        correct += outputs["mother name"] == (reference_outputs["mother name"].split()[0] if country == "India" else "")
        correct += outputs["middle name"] == ("" if country != "Philippines" else reference_outputs["middle name"])
        correct += outputs["surname"] == (reference_outputs["middle name"] if country == "India" else reference_outputs["last name"])

        return correct / 14
    
    except Exception as e:
        print(f"\nAn error occurred during field matching: {e}")
        traceback.print_exc()
        return 0

def full_passport(outputs: dict, reference_outputs: dict) -> bool:
    return field_match(outputs, reference_outputs) == 1      