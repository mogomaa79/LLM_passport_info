import csv
import os
from fuzzywuzzy import process, fuzz

class PlaceValidator:
    def __init__(self, data_dir="static", matching_threshold=80):
        self.data_dir = data_dir
        self.matching_threshold = matching_threshold
        
        if not os.path.exists(data_dir):
            os.makedirs(data_dir)
    
        self.cities = []
        
        self._load_data()
        
    def _load_data(self):
        custom_cities_file = os.path.join(self.data_dir, "custom_cities.csv")
        
        if os.path.exists(custom_cities_file):
            with open(custom_cities_file, 'r') as f:
                reader = csv.DictReader(f)
                custom_cities = list(reader)
                self.cities.extend(custom_cities)
    
    def validate_place(self, place_name, country):
        city_names = [city['name'] for city in self.cities if city['country_code'] == country]
        if not city_names:
            return {
                'input': place_name,
                'matched_name': "",
                'similarity_score': 0,
                'is_valid': False
            }
        
        best_match, score = process.extractOne(
            place_name, 
            city_names,
            scorer=fuzz.token_sort_ratio
        )
        
        return {
            'input': place_name,
            'matched_name': best_match,
            'similarity_score': score,
            'is_valid': score >= self.matching_threshold
        } 