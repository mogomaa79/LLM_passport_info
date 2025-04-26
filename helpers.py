import base64
import json
import os
import gspread
import pickle
from io import BytesIO
from PIL import Image
import pandas as pd
from pydantic import BaseModel, Field
from langchain_core.messages import HumanMessage
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

# remove pandas warning
pd.options.mode.chained_assignment = None  # default='warn'
# Define the required OAuth 2.0 scope
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',   # For Google Sheets access
    'https://www.googleapis.com/auth/drive.file'      # For Google Drive file access
]

try:
    with open("prompt.txt", "r", encoding="utf-8") as f:
        prompt = f.read()
except Exception as e:
    raise ValueError(f"Error reading prompt.txt: {e}")

def edit_agent_value(value, field):
    value = str(value).strip()
    
    # Check if it's a valid date in the format YYYY-MM-DD
    if pd.Series(value).str.match(r"^\d{4}-\d{2}-\d{2}$").any() and pd.to_datetime(value, errors='coerce') is not pd.NaT:
        # Convert to dd/mm/yyyy format
        return pd.to_datetime(value).strftime('%d/%m/%Y')

    elif str(field).strip().upper() == "NATIONALITY":
        return "IND"
    
    elif str(field).strip().upper() == "COUNTRY OF ISSUE" or str(field).strip().upper() == "PASSPORT PLACE(EN)" or str(field).strip().upper() == "BIRTH PLACE":
        return value.upper()

    elif str(field).strip().upper() == "GENDER":
        return value.upper()[0]

    else:
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
    #     "Last Name": "outputs.surname",
    #     "Middle Name": "outputs.middle name",
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
        "Last Name": "outputs.father name",
        "Middle Name": "outputs.surname",
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
    filtered_df.to_csv("results/filtered_df.csv", index=False)

    headers = filtered_df.columns.tolist()
    data = filtered_df.values.tolist()

    worksheet = gc.open_by_key(spreadsheet_id).sheet1
    worksheet.clear()

    data_to_upload = [headers] + [[str(item) for item in row] for row in data]

    worksheet.update('A1', data_to_upload)
    worksheet.freeze(rows=1)


def save_results(results, results_path):
    df = pd.DataFrame(results.to_pandas())
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