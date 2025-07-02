import re
from unidecode import unidecode

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
    import re
    from unidecode import unidecode
    
    def validate_passport_number(number_str):
        """Validate Philippine passport number with complex rules"""
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
    
    formatted_data["country"] = "PHL"
    
    place_of_issue = formatted_data.get("place of issue", "")
    if place_of_issue:
        derived_country = derive_country_of_issue(place_of_issue)
        if derived_country:
            formatted_data["country of issue"] = derived_country
    
    return formatted_data

def ethiopia_rules(formatted_data):
    formatted_data["place of issue"] = "ETHIOPIA"
    formatted_data["country of issue"] = "ETHIOPIA"

    # Number must be EQ then 7 digits or EP then 7 digits
    number = formatted_data.get("number", "")
    if len(number) < 9 or number[:2] not in ("EQ", "EP"): formatted_data["number"] = ""
    elif len(number) > 9: formatted_data["number"] = number[:9]

    return formatted_data

def nepal_rules(formatted_data):
    if "MOFA" in formatted_data.get("place of issue", ""):
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