import re
from unidecode import unidecode
import pandas as pd
from src.utils.results_utils import mapper
from src.utils.place_validator import PlaceValidator
from src.utils.country_rules import *

place_validator = PlaceValidator(matching_threshold=93)

def postprocess(json_data):
    formatted_data = dict(json_data)
    country = formatted_data["country"]

    string_fields = [
        "number", "country", "name", "surname", "middle name", "gender",
        "place of birth", "mother name", "father name", "place of issue", "country of issue"
    ]
    
    date_fields = [
        "birth date", "issue date", "expiry date",
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
    
    mrz_line1 = formatted_data.get("mrzLine1", "")
    mrz_line2 = formatted_data.get("mrzLine2", "")

    if not isinstance(mrz_line1, str): mrz_line1 = ""
    if not isinstance(mrz_line2, str): mrz_line2 = ""

    mrz_line1 = mrz_line1.strip()
    mrz_line2 = mrz_line2.strip()

    if len(mrz_line1) >= 44 and country != "LKA":
        name_part = mrz_line1[5:]
        if "<<" in name_part:
            surname_end = name_part.find("<<")
            if surname_end > 0 and mrz_line1[2:5] == country:
                surname = name_part[:surname_end].replace("<", " ").strip()
                formatted_data["mrz_surname"] = surname
                if surname:
                    clean_surname = re.sub(r'[^\w\s]', '', surname).upper().replace(" ", "")
                    clean_original = re.sub(r'[^\w\s]', '', formatted_data.get("surname", "")).upper().replace(" ", "")
                    if clean_original != clean_surname:
                        formatted_data["surname"] = surname
            
            names_start = name_part.find("<<") + 2
            if names_start < len(name_part):
                names_end = name_part[names_start:].find("<<")
                if names_end != -1:
                    given_names = name_part[names_start:names_end].replace("<", " ").strip()
                    original_name = formatted_data.get("name", "")
                    if original_name:
                        clean_original = re.sub(r'[^\w\s]', '', original_name).upper().replace(" ", "")
                        clean_mrz = re.sub(r'[^\w\s]', '', given_names).upper().replace(" ", "")

                        max_mrz_chars = len(name_part) - names_start
                        
                        if clean_original != clean_mrz and (len(clean_original) <= len(clean_mrz) and len(clean_original) <= max_mrz_chars):
                            formatted_data["name"] = given_names
                    else:
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
                century = 1900 if year >= pd.Timestamp.now().year - 2000 else 2000
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
                # current year - 2000 + 20 to account for 20 year extension
                century = 1900 if year >= pd.Timestamp.now().year - 2000 + 20 else 2000
                try:
                    date_obj = pd.to_datetime(f"{century + year}-{month}-{day}", errors='coerce')
                    if date_obj is not pd.NaT:
                        formatted_data["expiry date"] = date_obj.strftime('%d/%m/%Y')
                except:
                    pass
    
    # issue_place = str(formatted_data.get("place of issue", ""))
    # birth_place = str(formatted_data.get("place of birth", ""))

    # if issue_place and country:
    #     issue_place_result = place_validator.validate_issue_place(issue_place, country)
    #     if issue_place_result["is_valid"]:
    #         formatted_data["place of issue"] = issue_place_result["matched_name"]
    
    # if birth_place and country:
    #     birth_place_result = place_validator.validate_birth_place(birth_place, country)
    #     if birth_place_result["is_valid"]:
    #         formatted_data["place of birth"] = birth_place_result["matched_name"]
    
    # Format string fields
    for field in string_fields:
        if field in formatted_data:
            value = str(formatted_data[field]).upper()
            if value == "NAN": value = ""
            value = re.sub(r'[^\w\s]', ' ', value)
            # replace all diacritics with their base letter
            value = unidecode(value)
            value = re.sub(r'\s+', ' ', value)
            if value:
                formatted_data[field] = value.strip()
    
    # Format date fields
    for field in date_fields:
        if field in formatted_data:
            value = formatted_data[field]
            date_obj = pd.to_datetime(value, errors='coerce', dayfirst=True)
            formatted_data[field] = date_obj.strftime('%d/%m/%Y') if date_obj is not pd.NaT else value
    
    # Apply country-specific rules
    if country== "PHL": formatted_data = philippines_rules(formatted_data)
    if country == "NPL": formatted_data = nepal_rules(formatted_data)
    if country == "LKA": formatted_data = sri_lanka_rules(formatted_data)
    
    # Apply smart country-of-issue derivation for all countries if not already set
    if not formatted_data.get("country of issue", "").strip():
        place_of_issue = formatted_data.get("place of issue", "")
        if place_of_issue:
            from src.utils.country_rules import derive_country_of_issue
            derived_country = derive_country_of_issue(place_of_issue)
            if derived_country:
                formatted_data["country of issue"] = derived_country

    return formatted_data