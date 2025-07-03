import re
from fuzzywuzzy import fuzz

def correct_ocr_characters(text):
    if not text or not isinstance(text, str):
        return text
    
    # Common OCR character corrections
    corrections = {
        'O': '0',  # Letter O to digit 0
        'I': '1',  # Letter I to digit 1
        'S': '5',  # Letter S to digit 5
        'B': '8',  # Letter B to digit 8
        'G': '6',  # Letter G to digit 6
        'Z': '2',  # Letter Z to digit 2
        'l': '1',  # Lowercase L to digit 1
        'o': '0',  # Lowercase O to digit 0
        's': '5',  # Lowercase S to digit 5
        'g': '6',  # Lowercase G to digit 6
        'z': '2',  # Lowercase Z to digit 2
    }
    
    # Apply corrections
    corrected_text = ""
    for char in text:
        corrected_text += corrections.get(char, char)
    
    return corrected_text

def correct_ocr_digit_section(text, start_pos, end_pos):
    if not text or start_pos >= len(text) or end_pos > len(text) or start_pos >= end_pos:
        return text
    
    # Extract the section to correct
    section = text[start_pos:end_pos]
    corrected_section = correct_ocr_characters(section)
    
    # Reconstruct the text with corrected section
    return text[:start_pos] + corrected_section + text[end_pos:]

def derive_country_of_issue(place_of_issue):
    """
    Smart function to derive country of issue from place of issue.
    Handles various mapping rules and patterns.
    """
    if not place_of_issue or not isinstance(place_of_issue, str):
        return ""
    
    place = place_of_issue.strip().upper()
    
    # City to country mapping - comprehensive list
    city_country_map = {
        # Middle East
        "DUBAI": "UAE",
        "ABU DHABI": "UAE", 
        "SHARJAH": "UAE",
        "DOHA": "QATAR",
        "MANAMA": "BAHRAIN",
        "KUWAIT": "KUWAIT",
        "KUWAIT CITY": "KUWAIT",
        "RIYADH": "SAUDI ARABIA",
        "JEDDAH": "SAUDI ARABIA",
        "MAKKAH": "SAUDI ARABIA",
        "MECCA": "SAUDI ARABIA",
        "MEDINA": "SAUDI ARABIA",
        "MUSCAT": "OMAN",
        "BEIRUT": "LEBANON",
        "AMMAN": "JORDAN",
        "DAMASCUS": "SYRIA",
        "BAGHDAD": "IRAQ",
        "TEHRAN": "IRAN",
        "TEL AVIV": "ISRAEL",
        "JERUSALEM": "ISRAEL",
        
        # Asia Pacific
        "HONG KONG": "HONG KONG",
        "MACAU": "CHINA",
        "SINGAPORE": "SINGAPORE",
        "KUALA LUMPUR": "MALAYSIA",
        "JAKARTA": "INDONESIA",
        "BANGKOK": "THAILAND",
        "MANILA": "PHILIPPINES",
        "CEBU": "PHILIPPINES",
        "DAVAO": "PHILIPPINES",
        "SEOUL": "SOUTH KOREA",
        "TOKYO": "JAPAN",
        "TAIPEI": "TAIWAN",
        "BRUNEI": "BRUNEI",
        
        # Europe
        "LONDON": "UNITED KINGDOM",
        "MANCHESTER": "UNITED KINGDOM", 
        "BIRMINGHAM": "UNITED KINGDOM",
        "GLASGOW": "UNITED KINGDOM",
        "PARIS": "FRANCE",
        "BERLIN": "GERMANY",
        "ROME": "ITALY",
        "MADRID": "SPAIN",
        "BARCELONA": "SPAIN",
        "AMSTERDAM": "NETHERLANDS",
        "BRUSSELS": "BELGIUM",
        "VIENNA": "AUSTRIA",
        "ZURICH": "SWITZERLAND",
        "STOCKHOLM": "SWEDEN",
        "OSLO": "NORWAY",
        "COPENHAGEN": "DENMARK",
        "HELSINKI": "FINLAND",
        "MOSCOW": "RUSSIA",
        "ST PETERSBURG": "RUSSIA",
        "WARSAW": "POLAND",
        "PRAGUE": "CZECH REPUBLIC",
        "BUDAPEST": "HUNGARY",
        "ATHENS": "GREECE",
        "ISTANBUL": "TURKEY",
        "ANKARA": "TURKEY",
        
        # North America
        "NEW YORK": "UNITED STATES",
        "WASHINGTON": "UNITED STATES",
        "LOS ANGELES": "UNITED STATES",
        "CHICAGO": "UNITED STATES",
        "SAN FRANCISCO": "UNITED STATES",
        "TORONTO": "CANADA",
        "VANCOUVER": "CANADA",
        "MONTREAL": "CANADA",
        "OTTAWA": "CANADA",
        
        # Africa
        "CAIRO": "EGYPT",
        "LAGOS": "NIGERIA",
        "JOHANNESBURG": "SOUTH AFRICA",
        "CAPE TOWN": "SOUTH AFRICA",
        "NAIROBI": "KENYA",
        "ADDIS ABABA": "ETHIOPIA",
        "ACCRA": "GHANA",
        "CASABLANCA": "MOROCCO",
        "RABAT": "MOROCCO",
        "TUNIS": "TUNISIA",
        "ALGIERS": "ALGERIA",
        "TRIPOLI": "LIBYA",
        
        # South America
        "SAO PAULO": "BRAZIL",
        "RIO DE JANEIRO": "BRAZIL",
        "BRASILIA": "BRAZIL",
        "BUENOS AIRES": "ARGENTINA",
        "LIMA": "PERU",
        "BOGOTA": "COLOMBIA",
        "CARACAS": "VENEZUELA",
        "SANTIAGO": "CHILE",
        
        # Oceania
        "SYDNEY": "AUSTRALIA",
        "MELBOURNE": "AUSTRALIA",
        "PERTH": "AUSTRALIA",
        "BRISBANE": "AUSTRALIA",
        "WELLINGTON": "NEW ZEALAND",
        "AUCKLAND": "NEW ZEALAND"
    }
    
    # Rule 1: PE/PCG + City Mapping
    pe_match = re.match(r'^PE\s+(.+)$', place)
    if pe_match:
        city = pe_match.group(1).strip()
        if city in city_country_map:
            return city_country_map[city]
    
    pcg_match = re.match(r'^PCG\s+(.+)$', place)
    if pcg_match:
        city = pcg_match.group(1).strip()
        if city in city_country_map:
            return city_country_map[city]
    
    # Rule 2: Special Mapping Rules
    
    # DFA mapping - always Philippines
    if place.startswith("DFA"):
        return "PHILIPPINES"
    
    # MECO TAIPEI mapping - Philippines (consular office)
    if place == "MECO TAIPEI":
        return "PHILIPPINES"
    
    # HMPO mapping - United Kingdom
    if place.startswith("HMPO"):
        return "UNITED KINGDOM"
    
    # Rule 3: Stand-alone City Mapping
    if place in city_country_map:
        return city_country_map[place]
    
    # Rule 4: Smart pattern matching for unhandled cases
    
    # Handle consulate/embassy patterns
    consulate_patterns = [
        (r'CONSULATE.*GENERAL.*(\w+)', lambda m: city_country_map.get(m.group(1), "")),
        (r'EMBASSY.*(\w+)', lambda m: city_country_map.get(m.group(1), "")),
        (r'CONSUL.*(\w+)', lambda m: city_country_map.get(m.group(1), "")),
    ]
    
    for pattern, handler in consulate_patterns:
        match = re.search(pattern, place)
        if match:
            result = handler(match)
            if result:
                return result
    
    # Handle government/ministry patterns
    gov_patterns = [
        (r'MINISTRY.*FOREIGN.*AFFAIRS', ""),  # Could be home country
        (r'GOVERNMENT.*OF.*(\w+)', lambda m: m.group(1).upper()),
        (r'DEPT.*HOME.*AFFAIRS', ""),  # Usually home country
    ]
    
    for pattern, handler in gov_patterns:
        match = re.search(pattern, place)
        if match and callable(handler):
            result = handler(match)
            if result and result in ["PHILIPPINES", "NEPAL", "SRI LANKA", "INDIA", "KENYA", "ETHIOPIA", "UGANDA"]:
                return result
    
    # Handle passport office patterns
    if "PASSPORT OFFICE" in place:
        # Extract city before "PASSPORT OFFICE"
        city_match = re.search(r'(\w+).*PASSPORT OFFICE', place)
        if city_match:
            city = city_match.group(1).upper()
            if city in city_country_map:
                return city_country_map[city]
    
    # Fallback: Try to extract any recognizable city name from the place
    words = place.split()
    for word in words:
        if word in city_country_map:
            return city_country_map[word]
    
    return ""

def philippines_rules(formatted_data):  
    def process_number(number_str):
        if not number_str or not isinstance(number_str, str):
            return ""
        
        number = number_str.strip().upper()
        
        # Length check - must be exactly 9 characters
        if len(number) != 9:
            return ""
        
        # Prefix check - must start with 'P'
        if number[0] != "P":
            return ""
        
        # Digit block check - positions 2-8 must be digits
        # First convert letters that look like numbers using OCR correction
        number = correct_ocr_digit_section(number, 1, 8)
        
        if not number[1:8].isdigit():
            return ""
        
        # Last character processing
        last_char = number[8]
        if last_char in ("A", "B", "C"):
            # Already valid
            return number
        elif last_char == "8":
            # Convert 8 to B
            return number[:8] + "B"
        elif last_char == "0":
            # Convert 0 to C
            return number[:8] + "C"
        else:
            # Invalid character, reject
            return ""
    
    formatted_data["number"] = process_number(formatted_data.get("number", ""))

    place_of_issue = formatted_data.get("place of issue", "")
    if place_of_issue:
        derived_country = derive_country_of_issue(place_of_issue)
        if derived_country:
            formatted_data["country of issue"] = derived_country

    return formatted_data

def ethiopia_rules(formatted_data):
    def process_number(number_str):
        if not number_str or not isinstance(number_str, str):
            return ""
        
        number = number_str.strip().upper()
        
        # Length check - must be exactly 9 characters
        if len(number) != 9:
            return ""
        
        # Prefix check - must start with 'EQ' or 'EP'
        if not (number.startswith("EQ") or number.startswith("EP")):
            return ""
        
        # Digit block check - positions 3-9 must be digits
        # First convert letters that look like numbers using OCR correction
        number = correct_ocr_digit_section(number, 2, 9)
        
        # Validate that positions 3-9 are digits
        if not number[2:].isdigit():
            return ""
        
        return number
    
    formatted_data["number"] = process_number(formatted_data.get("number", ""))
    formatted_data["place of issue"] = "ETHIOPIA"
    formatted_data["country of issue"] = "ETHIOPIA"

    return formatted_data

def kenya_rules(formatted_data):
    def process_number(number_str):
        if not number_str or not isinstance(number_str, str):
            return ""
        
        number = number_str.strip().upper()
        
        # Length check - must be exactly 9 characters
        if len(number) < 8: return ""
        elif len(number) > 9: number = number[:9]
        
        if not (number.startswith("AK") or number.startswith("BK") or number.startswith("CK")): return ""

        number = correct_ocr_digit_section(number, 2, 8)
        
        # Validate that positions 3-9 are digits
        if not number[2:].isdigit():
            return ""
        
        return number
    
    def fuzzy_match_place_of_issue(place_str):
        if not place_str or not isinstance(place_str, str):
            return ""
        
        place = place_str.strip().upper()
        
        # Target patterns for fuzzy matching
        target_patterns = {
            "GOVERNMENT OF KENYA": 80,
            "REGISTRAR GENERAL HRE": 80,
        }
        
        # Find best match using fuzzywuzzy
        best_match = None
        best_score = 0
        
        for pattern, threshold in target_patterns.items():
            score = fuzz.ratio(place, pattern)
            if score >= threshold and score > best_score:
                best_match = pattern
                best_score = score
        
        if not best_match:
            print(f"No best match found for {place_str}")
        return best_match if best_match else place_str
    
    # Process passport number
    formatted_data["number"] = process_number(formatted_data.get("number", ""))
    
    if place_of_issue := formatted_data.get("place of issue", ""):
        normalized_place = fuzzy_match_place_of_issue(place_of_issue)
        formatted_data["place of issue"] = normalized_place
    
    formatted_data["country of issue"] = "KENYA"
    
    if place_of_birth := formatted_data.get("place of birth", ""):
        place_of_birth = re.sub(r',\s*KEN$', '', place_of_birth, flags=re.IGNORECASE)
        place_of_birth = re.sub(r'\s+KEN$', '', place_of_birth, flags=re.IGNORECASE)
        formatted_data["place of birth"] = place_of_birth.strip()
    
    surname = formatted_data.get("surname", "")
    if surname:
        formatted_data["surname"] = surname.replace("<", " ").strip()
    
    return formatted_data

def nepal_rules(formatted_data):
    def fuzzy_match_place_of_issue(place_str):
        if not place_str or not isinstance(place_str, str):
            return ""
        
        place = place_str.strip().upper()
        
        # Target pattern for fuzzy matching
        target_pattern = "MOFA DEPARTMENT OF PASSPORTS"
        
        # Use partial ratio for substring matching (more lenient)
        partial_score = fuzz.partial_ratio(place, target_pattern)
        full_score = fuzz.ratio(place, target_pattern)
        
        # Lower threshold for more lenient matching
        if partial_score >= 60 or full_score >= 50:
            return "MOFA DEPARTMENT OF PASSPORTS"
        
        # Additional check for key words
        key_words = ["MOFA", "PASSPORT", "DEPARTMENT"]
        words_in_place = place.split()
        matches = sum(1 for word in key_words if any(fuzz.ratio(word, place_word) >= 70 for place_word in words_in_place))
        
        # If at least 2 key words match, consider it a match
        if matches >= 2:
            return "MOFA DEPARTMENT OF PASSPORTS"
        
        # Even more lenient check - if "MOFA" appears anywhere
        if "MOFA" in place or any(fuzz.ratio("MOFA", word) >= 80 for word in words_in_place):
            return "MOFA DEPARTMENT OF PASSPORTS"
        
        return place_str
    
    # Process place of issue with fuzzy matching
    if place_of_issue := formatted_data.get("place of issue", ""):
        normalized_place = fuzzy_match_place_of_issue(place_of_issue)
        if normalized_place == "MOFA DEPARTMENT OF PASSPORTS":
            formatted_data["place of issue"] = "MOFA"
            formatted_data["country of issue"] = "NEPAL"
    
    number = formatted_data.get("number", "")
    if len(number) < 6: formatted_data["number"] = ""
    elif len(number) > 9: formatted_data["number"] = number[:9]
        
    return formatted_data

def sri_lanka_rules(formatted_data):
    formatted_data["surname"] = formatted_data.get("surname", "").replace("<", " ")
    place_of_issue = formatted_data.get("place of issue", "")
    if "COLOMBO" in place_of_issue:
        formatted_data["place of issue"] = "COLOMBO"
        formatted_data["country of issue"] = "SRI LANKA"
    
    number = formatted_data.get("number", "")
    if len(number) < 6: formatted_data["number"] = ""
    elif len(number) > 9: formatted_data["number"] = number[:9]

    return formatted_data

def india_rules(formatted_data):
    number = formatted_data.get("number", "")
    if len(number) < 9: formatted_data["number"] = ""
    elif len(number) > 9: formatted_data["number"] = number[:9]

    return formatted_data

