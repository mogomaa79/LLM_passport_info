def philippines_rules(formatted_data):
    number = formatted_data.get("number").upper()
    if not number:
        return ""
    
    if len(number) != 9 or number[0] != "P" or not number[1:8].isdigit():
        return ""
    
    last = number[8]
    if last not in ("A", "B", "C"):
        if last == "8":
            last = "B"
            number = number[:8] + last
        elif last == "0":
            last = "C"
            number = number[:8] + last
        else:
            return ""
    formatted_data["number"] = number
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