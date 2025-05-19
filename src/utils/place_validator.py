import csv
import os
from fuzzywuzzy import process, fuzz

class PlaceValidator:
    def __init__(self, data_dir="static", matching_threshold=90):
        self.data_dir = data_dir
        self.matching_threshold = matching_threshold
        
        if not os.path.exists(data_dir):
            os.makedirs(data_dir)
    
        self.cities = []
        self.issue_places = []
        
        self._load_data()
        
    def _load_data(self):
        custom_cities_file = os.path.join(self.data_dir, "birthplaces.csv")
        issue_places_file = os.path.join(self.data_dir, "issueplaces.csv")

        if os.path.exists(custom_cities_file):
            with open(custom_cities_file, 'r') as f:
                reader = csv.DictReader(f)
                custom_cities = list(reader)
                self.cities.extend(custom_cities)

        if os.path.exists(issue_places_file):
            with open(issue_places_file, 'r') as f:
                reader = csv.DictReader(f)
                issue_places = list(reader)
                self.issue_places.extend(issue_places)
    
    def validate_issue_place(self, place_name, country):
        issue_places = [place for place in self.issue_places if place['country_code'] == country]
        if not issue_places:
            return {
                'input': place_name,
                'matched_name': "",
                'similarity_score': 0,
                'is_valid': False
            }
        
        best_match, score = process.extractOne(
            place_name, 
            [place['name'] for place in issue_places],
            scorer=fuzz.token_sort_ratio
        )
        
        return {
            'input': place_name,
            'matched_name': best_match,
            'similarity_score': score,
            'is_valid': score >= self.matching_threshold
        }
    

    def validate_birth_place(self, place_name, country):
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