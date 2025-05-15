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

def nepal_rules(formatted_data):
    place_of_issue = formatted_data.get("place of issue")
    if "MOFA" in place_of_issue:
        formatted_data["place of issue"] = "MOFA"
        formatted_data["country of issue"] = "NEPAL"
    return formatted_data

def sri_lanka_rules(formatted_data):
    return formatted_data