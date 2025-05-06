import base64
import json
import os
import re
import gspread
import pickle
from io import BytesIO
from PIL import Image
import pandas as pd
from pydantic import BaseModel, Field
from langchain_core.messages import HumanMessage
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from PlaceValidator import PlaceValidator
from unidecode import unidecode

# Initialize the place validator
place_validator = PlaceValidator()

# remove pandas warning
pd.options.mode.chained_assignment = None  # default='warn'
# Define the required OAuth 2.0 scope
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',   # For Google Sheets access
    'https://www.googleapis.com/auth/drive.file'      # For Google Drive file access
]

try:
    with open("prompts/Philippines.txt", "r", encoding="utf-8") as f:
        prompt = f.read()
except Exception as e:
    raise ValueError(f"Error reading prompt.txt: {e}")

def edit_agent_value(value, field):
    value = str(value).strip().upper()

    if pd.Series(value).str.match(r"^\d{4}-\d{2}-\d{2}$").any() and pd.to_datetime(value, errors='coerce') is not pd.NaT:
        return pd.to_datetime(value).strftime('%d/%m/%Y')

    elif str(field).strip().upper() == "NATIONALITY":
        return "PHL"
    
    elif str(field).strip().upper() == "MOTHER NAME" or str(field).strip().upper() == "FATHER NAME":
        return ""

    elif str(field).strip().upper() == "GENDER":
        return value[0]

    return value

def upload_results(csv_file_path: str, spreadsheet_id: str, credentials_path: str):
    # Token file to store user credentials
    token_file = 'token.pickle'

    # Check if token file exists and is valid
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
                credentials_path, SCOPES)
            creds = flow.run_local_server(port=0)

        # Save the credentials for the next time
        with open(token_file, 'wb') as token:
            pickle.dump(creds, token)

    # Now authorize the credentials
    gc = gspread.authorize(creds)

    df = pd.read_csv(csv_file_path)
    all_df = pd.read_excel("OCR Extracted Data and User Modifications (feb 1- march 31) .xlsx", sheet_name="Data")
    all_df = all_df.ffill()
    merged_df = pd.merge(df, all_df, left_on="inputs.image_id", right_on="Maid’s ID", how="left")

    # google_sheet_columns = {
    #     "Birth Place": "outputs.place of birth",
    #     "Birthdate": "outputs.birth date",
    #     "Country of Issue": "outputs.country of issue",
    #     "First Name": "outputs.name",
    #     "Gender": "outputs.gender",
    #     "Last Name": "outputs.father name",
    #     "Middle Name": "outputs.surname",
    #     "Mother Name": "outputs.mother name",
    #     "Nationality": "outputs.country",
    #     "Passport Expiry Date": "outputs.expiry date",
    #     "Passport Issue Date": "outputs.issue date",
    #     "Passport Place(EN)": "outputs.place of issue",
    #     "Passport ID": "outputs.number",
    # }
    google_sheet_columns = {
        "Birth Place": "outputs.place of birth",
        "Birthdate": "outputs.birth date",
        "Country of Issue": "outputs.country of issue",
        "First Name": "outputs.name",
        "Gender": "outputs.gender",
        "Last Name": "outputs.surname",
        "Middle Name": "outputs.middle name",
        "Mother Name": "outputs.mother name",
        "Nationality": "outputs.country",
        "Passport Expiry Date": "outputs.expiry date",
        "Passport Issue Date": "outputs.issue date",
        "Passport Place(EN)": "outputs.place of issue",
        "Passport ID": "outputs.number",
    }

    def get_gemini_value(series):
        maid_id = series['Maid’s ID']
        field = series["Modified Field"]
        mapped_field = google_sheet_columns.get(field)
        if mapped_field:
            # get from df maid_id, field
            row = df[df["inputs.image_id"] == maid_id]
            if row.empty:
                return ""
            else:
                row = row.iloc[0]
                gemini_value = row.get(mapped_field)
            if pd.isna(gemini_value):
                return ""
            else:
                return gemini_value
        else:
            return ""
        
    filtered_df = merged_df[['Maid’s ID', 'Modified Field', 'Agent Value', 'OCR Value']]
    filtered_df["Gemini Value"] = filtered_df.apply(get_gemini_value, axis=1)
    filtered_df["Edited Agent Value"] = filtered_df.apply(lambda row: edit_agent_value(row['Agent Value'], row['Modified Field']), axis=1)
    filtered_df["Similarity"] = filtered_df.apply(lambda row: row['Gemini Value'] == row['Edited Agent Value'], axis=1)
    filtered_df = filtered_df[['Maid’s ID', 'Modified Field', 'Edited Agent Value', 'Gemini Value', 'Similarity', 'Agent Value', 'OCR Value']]

    filtered_df['Maid’s ID'] = filtered_df['Maid’s ID'].astype(int)

    headers = filtered_df.columns.tolist()
    data = filtered_df.values.tolist()

    worksheet = gc.open_by_key(spreadsheet_id).sheet1
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

def map_input_to_messages_lambda(inputs: dict):
    multimodal_prompt = inputs.get("multimodal_prompt")
    multimodal_prompt.insert(0, {"type": "text", "text": prompt})
    messages = [
        HumanMessage(content=multimodal_prompt),
    ]
    
    return messages

def postprocess(json_data):
    formatted_data = dict(json_data)

    string_fields = [
        "number", "country", "name", "surname", "middle name", "gender",
        "place of birth", "mother name", "father name", "place of issue", "country of issue"
    ]
    
    date_fields = [
        "original birth date", "birth date", "issue date", 
        "original expiry date", "expiry date", "mrzDateOfBirth", "mrzDateOfExpiry"
    ]
    
    # Helper function to validate MRZ checksums
    def calculate_checksum(input_string):
        weights = [7, 3, 1]
        total = 0
        for i, char in enumerate(input_string):
            if char.isdigit():
                value = int(char)
            elif char == '<':
                value = 0
            else:
                value = ord(char) - 55  # A=10, B=11, etc.
            total += value * weights[i % 3]
        return total % 10
    
    mrz_line1 = formatted_data.get("mrzLine1", "").strip()
    mrz_line2 = formatted_data.get("mrzLine2", "").strip()

    if len(mrz_line1) >= 44:    
        name_part = mrz_line1[5:] if len(mrz_line1) > 5 else ""
        if "<<" in name_part:
            surname_end = name_part.find("<<")
            if surname_end > 0:
                surname = name_part[:surname_end].replace("<", " ").strip()
                if surname:
                    formatted_data["surname"] = surname
            
            names_start = name_part.find("<<") + 2
            if names_start < len(name_part):
            
                given_names = name_part[names_start:].replace("<", " ").strip()
                if given_names:
                    formatted_data["name"] = given_names
    

    if len(mrz_line2) >= 10:
        doc_number = mrz_line2[:9].replace("<", "").strip()
        doc_number_check = mrz_line2[9]
        if doc_number and doc_number_check.isdigit():
            calculated_check = str(calculate_checksum(doc_number.ljust(9, '<')))
            if calculated_check == doc_number_check or not doc_number_check.isdigit():
                formatted_data["number"] = doc_number
    
    if len(mrz_line2) >= 20: 
        birth_date = mrz_line2[13:19]
        birth_date_check = mrz_line2[19]

        if birth_date.isdigit() and birth_date_check.isdigit():
            year = int(birth_date[:2])
            month = int(birth_date[2:4])
            day = int(birth_date[4:6])
            
            if 1 <= month <= 12 and 1 <= day <= 31:
                century = 1900 if year >= 40 else 2000
                try:
                    date_obj = pd.to_datetime(f"{century + year}-{month}-{day}", errors='coerce')
                    if date_obj is not pd.NaT:
                        formatted_data["birth date"] = date_obj.strftime('%d/%m/%Y')
                except:
                    pass
    
    if len(mrz_line2) >= 21:
        gender = mrz_line2[20]
        if gender in ["M", "F"]:
            formatted_data["gender"] = gender
    
    if len(mrz_line2) >= 28:  # Include checksum digit
        expiry_date = mrz_line2[21:27]
        expiry_date_check = mrz_line2[27]
        if expiry_date.isdigit() and expiry_date_check.isdigit():
            year = int(expiry_date[:2])
            month = int(expiry_date[2:4])
            day = int(expiry_date[4:6])

            if 1 <= month <= 12 and 1 <= day <= 31:
                century = 1900 if year >= 40 else 2000
                try:
                    date_obj = pd.to_datetime(f"{century + year}-{month}-{day}", errors='coerce')
                    if date_obj is not pd.NaT:
                        formatted_data["expiry date"] = date_obj.strftime('%d/%m/%Y')
                except:
                    pass
    
    country = formatted_data.get("country", "")
    issue_place = formatted_data.get("place of issue", "")
    birth_place = formatted_data.get("place of birth", "")

    if issue_place and country:
        issue_place_result = place_validator.validate_place(issue_place, country)
        if issue_place_result["is_valid"]:
            formatted_data["place of issue"] = issue_place_result["matched_name"]
    
    if birth_place and country:
        birth_place_result = place_validator.validate_place(birth_place, country)
        if birth_place_result["is_valid"]:
            formatted_data["place of birth"] = birth_place_result["matched_name"]
    
    # Format string fields
    for field in string_fields:
        if field in formatted_data:
            value = str(formatted_data[field]).upper()
            value = re.sub(r'[^\w\s]', ' ', value)
            # replace all diacritics with their base letter
            value = unidecode(value)
            value = re.sub(r'\s+', ' ', value).strip()
            formatted_data[field] = value
    
    # Format date fields
    for field in date_fields:
        if field in formatted_data:
            value = formatted_data[field]
            date_obj = pd.to_datetime(value, errors='coerce', dayfirst=True)
            formatted_data[field] = date_obj.strftime('%d/%m/%Y') if date_obj is not pd.NaT else value
    
    return formatted_data

class PassportExtraction(BaseModel):
    """Detailed passport information extracted from an image."""
    original_number: str = Field(alias="original number")
    number: str
    original_country: str = Field(alias="original country")
    country: str
    name: str
    surname: str
    middle_name: str = Field(alias="middle name")
    original_gender: str = Field(alias="original gender")
    gender: str
    place_of_birth: str = Field(alias="place of birth")
    original_birth_date: str = Field(alias="original birth date")
    birth_date: str = Field(alias="birth date")
    issue_date: str = Field(alias="issue date")
    original_expiry_date: str = Field(alias="original expiry date")
    expiry_date: str = Field(alias="expiry date")
    mother_name: str = Field(alias="mother name")
    father_name: str = Field(alias="father name")
    place_of_issue: str = Field(alias="place of issue")
    country_of_issue: str = Field(alias="country of issue")
    mrzLine1: str
    mrzLine2: str
    mrzPassportNumber: str
    mrzDateOfBirth: str
    mrzDateOfExpiry: str
    mrzSex: str
    mrzSurname: str
    mrzGivenNames: str