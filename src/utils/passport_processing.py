import re
from unidecode import unidecode
import pandas as pd
from langchain_core.messages import HumanMessage
from src.utils.place_validator import PlaceValidator

DATASET_NAME = "Kenya"
place_validator = PlaceValidator()

def get_prompt():
    """Load the prompt for a specific country"""
    try:
        with open(f"prompts/{DATASET_NAME}.txt", "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        raise ValueError(f"Error reading prompt file for {DATASET_NAME}: {e}")

def map_input_to_messages_lambda(inputs: dict):
    """Convert inputs to LangChain messages format"""
    multimodal_prompt = inputs.get("multimodal_prompt")
    prompt_text = get_prompt()
    
    multimodal_prompt.insert(0, {"type": "text", "text": prompt_text})
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