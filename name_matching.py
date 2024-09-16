from rapidfuzz import process, fuzz
import fuzzy  # For Double Metaphone
import sys
import logging
from speakcare_logging import create_logger

# NameMatcher class that provides a method to find the best match for a given name

class NameMatcher:
    def __init__(self, primary_threshold=90, secondary_threshold=80):
        self.primary_threshold = primary_threshold
        self.secondary_threshold = secondary_threshold
        self.logger = create_logger(__name__)
        
    def get_best_match(self, input_name= None, names_to_match = None):
        # Initial character-based matching
        best_match, score, best_idx = process.extractOne(input_name, names_to_match, scorer=fuzz.WRatio)
        
        if score >= self.primary_threshold:
            self.logger.debug(f"Found best match by WRatio'{best_match}' with score {score}")
            return best_match, names_to_match.index(best_match), score

        # Fallback to phonetic matching
        dmetaphone = fuzzy.DMetaphone()
        input_primary, input_secondary = dmetaphone(input_name)
        potential_matches = []

        # Check phonetic similarity
       #best_secondary_score = self.secondary_threshold
        best_secondary_score = 0
        best_match_index = None
        for i, name in enumerate(names_to_match):
            name_primary, name_secondary = dmetaphone(name)
            if (input_primary == name_primary or input_primary == name_secondary or
                input_secondary == name_primary or input_secondary == name_secondary):

                #secondary_match, secondary_score, _ = process.extractOne(name, [input_name], scorer=fuzz.WRatio)
                secondary_score = fuzz.WRatio(name, input_name)
                # Collect matches that are phonetically similar with reasonable character match
                if secondary_score >= best_secondary_score:
                    best_secondary_score = secondary_score
                    best_match = name
                    best_match_index = i

        # found a phonetic match and the character distance is within the threshold
        if best_secondary_score >= self.secondary_threshold:
            self.logger.debug(f"Found best match by Double Metaphone '{best_match}' with score {best_secondary_score}")
            return best_match, best_match_index, best_secondary_score
        
        # found a phonetic match but the character distance score is too low
        if best_secondary_score > 0:
            self.logger.debug(f"Best match by Double Metaphone '{best_match}' score {best_secondary_score} is lower than threshold {self.secondary_threshold}")
        
        else:
            self.logger.debug(f"No match found for '{input_name}'")

        return None, None, None
        

    def filter_by_metaphone(input_name, patient_names):
        """
        Filters the patient names based on Double Metaphone similarity with the input name.
        Returns a list of indices of matching names.
        """
        dmetaphone = fuzzy.DMetaphone()
        input_primary, input_secondary = dmetaphone(input_name)
        
        matching_indices = []
        
        for i, name in enumerate(patient_names):
            name_primary, name_secondary = dmetaphone(name)
            
            # Check if either primary or secondary metaphone matches
            if (input_primary == name_primary) or (input_primary == name_secondary) or \
            (input_secondary == name_primary) or (input_secondary == name_secondary):
                matching_indices.append(i)
        
        return matching_indices




# Example usage
def main(argv):  
    patient_names = ["John Smith", "Jane Doe", "Johnathan Smyth", "Johnny Appleseed", "Jaine Do", "Jon Smythen"]
    input_name = "Jonny Smyth"  # Example transcribed name

    matcher = NameMatcher(primary_threshold=90, secondary_threshold=75)
    best_match_index, score = matcher.get_best_match(input_name, patient_names)

    if best_match_index is not None:
        print(f"Best match for '{input_name}' is: '{patient_names[best_match_index]}' (Index: {best_match_index}) with score: {score}") 
    else:
        print(f"No match found for '{input_name}'")

if __name__ == "__main__":
    main(sys.argv[1:])