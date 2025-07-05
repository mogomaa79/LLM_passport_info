import re
from unidecode import unidecode
import pandas as pd
from src.utils.results_utils import mapper
from src.utils.place_validator import PlaceValidator
from src.utils.country_rules import *

place_validator = PlaceValidator(matching_threshold=93)

def postprocess(json_data):
    """
    Postprocess extraction results, handling both regular strings and CertainField objects.
    Preserves certainty information throughout the process.
    """
    formatted_data = dict(json_data)
    
    # Helper function to extract string value from CertainField or regular string
    def get_string_value(field_value):
        if field_value is None:
            return ""
        if hasattr(field_value, '__str__'):
            str_value = str(field_value)
            # Handle "nan", "NaN", "NAN" strings specifically
            if str_value.lower() in ['nan', 'none', 'null']:
                return ""
            return str_value
        return str(field_value) if field_value else ""
    
    # Helper function to get certainty from CertainField
    def get_certainty(field_value):
        if hasattr(field_value, 'certainty'):
            return field_value.certainty
        return False
    
    # Helper function to update field while preserving certainty
    def update_field_with_certainty(field_name, new_value, certainty=False):
        old_field = formatted_data.get(field_name, "")
        
        # Handle None values
        if new_value is None:
            new_value = ""
        
        # Import here to avoid circular imports
        try:
            from src.passport_extraction import CertainField
            formatted_data[field_name] = CertainField(str(new_value), certainty)
        except ImportError:
            # Fallback if import fails
            formatted_data[field_name] = str(new_value) if new_value is not None else ""

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
    
    # Extract string values for MRZ processing
    mrz_line1 = get_string_value(formatted_data.get("mrzLine1", ""))
    mrz_line2 = get_string_value(formatted_data.get("mrzLine2", ""))

    if not isinstance(mrz_line1, str): mrz_line1 = ""
    if not isinstance(mrz_line2, str): mrz_line2 = ""

    mrz_line1 = mrz_line1.strip()
    mrz_line2 = mrz_line2.strip()

    mrz_country_l1 = mrz_line1[2:5]
    mrz_country_l2 = mrz_line2[9:13]

    if mrz_country_l1 in mapper.values():
        update_field_with_certainty("country", mrz_country_l1)
    if mrz_country_l2 in mapper.values():
        update_field_with_certainty("country", mrz_country_l2)

    country = get_string_value(formatted_data.get("country", ""))

    if len(mrz_line1) >= 8 and country not in ["LKA", "IND"]: 
        surname_start_pos = -1
        if country and len(country) == 3:
            # Look for the country code in MRZ line 1
            country_pos = mrz_line1.find(country)
            if country_pos >= 0:
                surname_start_pos = country_pos + 3  # Start after the 3-letter country code
        
        # Fallback to position 5 if country code not found
        if surname_start_pos == -1:
            surname_start_pos = 5
        
        name_part = mrz_line1[surname_start_pos:] if len(mrz_line1) > surname_start_pos else ""
        
        # Get OCR name lengths for guidance
        ocr_surname = get_string_value(formatted_data.get("surname", ""))
        ocr_name = get_string_value(formatted_data.get("name", ""))
        
        if name_part and "<<" in name_part:
            surname_end = name_part.find("<<")
            
            if surname_end > 0:
                surname = name_part[:surname_end].replace("<", " ").strip()
                formatted_data["mrz_surname"] = surname
                
                if surname:
                    clean_surname = re.sub(r'[^\w\s]', '', surname).upper().replace(" ", "")
                    clean_original = re.sub(r'[^\w\s]', '', ocr_surname).upper().replace(" ", "")
                    if clean_surname != clean_original:
                        update_field_with_certainty("surname", surname, certainty=False)
            
            names_start = name_part.find("<<") + 2
            if names_start < len(name_part) and names_start >= 2:
                names_end = name_part[names_start:].find("<<")
                if names_end != -1:
                    given_names = name_part[names_start:names_start + names_end].replace("<", " ").strip()
                else:
                    # Use all remaining characters if no second "<<" found (incomplete MRZ)
                    given_names = name_part[names_start:].replace("<", " ").strip()
                
                if given_names:
                    clean_mrz = re.sub(r'[^\w\s]', '', given_names).upper().replace(" ", "")
                    clean_original = re.sub(r'[^\w\s]', '', ocr_name).upper().replace(" ", "")
                    
                    if (not clean_original or len(clean_original) < 3 or
                        (len(clean_mrz) >= len(clean_original) and clean_original != clean_mrz)):
                        update_field_with_certainty("name", given_names)
    
    if len(mrz_line2) >= 10:
        doc_number = mrz_line2[:9].replace("<", "").strip()
        doc_number_check = mrz_line2[9]
        if doc_number and doc_number_check.isdigit():
            calculated_check = str(calculate_checksum(doc_number.ljust(9, '<')))
            if calculated_check == doc_number_check or not doc_number_check.isdigit():
                update_field_with_certainty("number", doc_number)
    
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
                        update_field_with_certainty("birth date", date_obj.strftime('%d/%m/%Y'))
                except:
                    pass
    
    if len(mrz_line2) >= 21:
        gender = mrz_line2[20]
        if gender in ["M", "F"]:
            update_field_with_certainty("gender", gender)
    
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
                        update_field_with_certainty("expiry date", date_obj.strftime('%d/%m/%Y'))
                except:
                    pass
    
    # Format string fields while preserving certainty
    for field in string_fields:
        if field in formatted_data:
            value = get_string_value(formatted_data[field]).upper()
            # Handle various representations of empty/null values
            if value in ["NAN", "NONE", "NULL", "N/A", "NA"]:
                value = ""
            value = re.sub(r'[^\w\s]', ' ', value)
            # replace all diacritics with their base letter
            value = unidecode(value)
            value = re.sub(r'\s+', ' ', value)
            if value:
                update_field_with_certainty(field, value.strip())
            else:
                # Explicitly set empty fields to empty CertainField
                update_field_with_certainty(field, "")
    
    # Format date fields while preserving certainty
    for field in date_fields:
        if field in formatted_data:
            value = get_string_value(formatted_data[field])
            date_obj = pd.to_datetime(value, errors='coerce', dayfirst=True)
            formatted_value = date_obj.strftime('%d/%m/%Y') if date_obj is not pd.NaT else value
            update_field_with_certainty(field, formatted_value)
    
    # Apply country-specific rules (these functions will need to be updated to handle CertainField)
    # For now, convert to regular dict for processing, then convert back
    regular_dict = {}
    certainty_map = {}
    
    for key, value in formatted_data.items():
        regular_dict[key] = get_string_value(value)
        certainty_map[key] = get_certainty(value)
    
    # Apply country-specific rules
    country_str = get_string_value(formatted_data.get("country", ""))
    if country_str == "PHL": regular_dict = philippines_rules(regular_dict)
    if country_str == "ETH": regular_dict = ethiopia_rules(regular_dict)
    if country_str == "KEN": regular_dict = kenya_rules(regular_dict)
    if country_str == "NPL": regular_dict = nepal_rules(regular_dict)
    if country_str == "LKA": regular_dict = sri_lanka_rules(regular_dict)
    if country_str == "UGA": regular_dict = uganda_rules(regular_dict)
    if country_str == "IND": regular_dict = india_rules(regular_dict)
    
    # Apply smart country-of-issue derivation for all countries if not already set
    if not regular_dict.get("country of issue", "").strip():
        place_of_issue = regular_dict.get("place of issue", "")
        if place_of_issue:
            from src.utils.country_rules import derive_country_of_issue
            derived_country = derive_country_of_issue(place_of_issue)
            if derived_country:
                regular_dict["country of issue"] = derived_country

    # Convert back to CertainField objects with preserved certainty
    try:
        from src.passport_extraction import CertainField
        for key, value in regular_dict.items():
            certainty = certainty_map.get(key, False)
            # Handle None values
            if value is None:
                value = ""
            formatted_data[key] = CertainField(str(value), certainty)
    except ImportError:
        # Fallback if import fails
        formatted_data = regular_dict

    # Final pass: ensure all None values are converted to empty CertainField objects
    try:
        from src.passport_extraction import CertainField
        for key, value in formatted_data.items():
            if value is None:
                formatted_data[key] = CertainField("", False)
            elif not isinstance(value, CertainField):
                # Convert regular values to CertainField objects
                formatted_data[key] = CertainField(str(value) if value is not None else "", False)
    except ImportError:
        # Fallback if import fails
        for key, value in formatted_data.items():
            if value is None:
                formatted_data[key] = ""

    return formatted_data