#!/usr/bin/env python3

from typing import Dict, Tuple, List, Optional, NamedTuple
from rapidfuzz import fuzz
import fuzzy  # For Double Metaphone
import jellyfish  # For Soundex
import re
from speakcare_logging import SpeakcareLogger

# Enhanced NameMatcher class optimized for transcript processing with fuzzy matching
# Uses Jaro-Winkler + Soundex + Double Metaphone for comprehensive similarity

class NameComponents(NamedTuple):
    """Structure for parsed name components"""
    first_name: Optional[str]
    last_name: Optional[str] 
    nickname: Optional[str]

class MatchCandidate(NamedTuple):
    """Structure for a single match candidate"""
    matched_id: int
    matched_name: str
    confidence_score: float
    component_scores: Dict[str, float]  # scores for first_name, last_name, nickname
    match_type: str  # 'first_name', 'last_name', 'nickname', with '+' between them

class MatchResult(NamedTuple):
    """Structure for match results - can contain multiple candidates"""
    primary_match: Optional[MatchCandidate]  # Best match
    all_candidates: List[MatchCandidate]     # Best 3 matches found
    is_ambiguous: bool                       # True if multiple close matches found

class NameMatcher:
    def __init__(self, high_confidence_threshold=75, medium_confidence_threshold=55, 
                 min_confidence=35, ambiguity_threshold=10):
        """
        Initialize NameMatcher optimized for transcript processing (lower thresholds)
        
        Args:
            high_confidence_threshold: Threshold for high-confidence matches (lowered for transcripts)
            medium_confidence_threshold: Threshold for medium-confidence matches
            min_confidence: Minimum confidence score to avoid false negatives
            ambiguity_threshold: If multiple matches are within this many points, consider ambiguous
        """
        self.high_threshold = high_confidence_threshold
        self.medium_threshold = medium_confidence_threshold
        self.min_confidence = min_confidence
        self.ambiguity_threshold = ambiguity_threshold
        self.logger = SpeakcareLogger(NameMatcher.__name__)
        self.dmetaphone = fuzzy.DMetaphone()
        
    def tokenize_name(self, input_name: str) -> NameComponents:
        """
        Tokenize input name - for transcript context, usually just a single extracted name
        """
        if not input_name or not input_name.strip():
            return NameComponents(None, None, None)
            
        # Clean and normalize the input
        cleaned_name = re.sub(r'[^\w\s]', '', input_name.strip())
        name_parts = cleaned_name.split()
        
        if not name_parts:
            return NameComponents(None, None, None)
            
        if len(name_parts) == 1:
            # Single name from transcript - could match any field
            name = name_parts[0].lower()
            return NameComponents(first_name=name, last_name=name, nickname=name)
            
        elif len(name_parts) == 2:
            # Two parts - likely first and last name
            first_name = name_parts[0].lower()
            last_name = name_parts[1].lower()
            return NameComponents(first_name=first_name, last_name=last_name, nickname=first_name)
            
        else:
            # Multiple parts - combine first parts as first name, last part as last name
            first_name = " ".join(name_parts[:-1]).lower()
            last_name = name_parts[-1].lower()
            nickname = name_parts[0].lower()  # Use first word as potential nickname
            return NameComponents(first_name=first_name, last_name=last_name, nickname=nickname)

    def _calculate_similarity_score(self, input_name: str, target_name: str) -> float:
        """
        Calculate comprehensive similarity score using multiple algorithms
        Optimized for transcript processing with emphasis on phonetic matching
        """
        if not input_name or not target_name:
            return 0.0
            
        input_clean = input_name.lower()
        target_clean = target_name.lower()
        
        # 1. Character-based similarity using Jaro-Winkler (better for names)
        jaro_winkler_score = fuzz.ratio(input_clean, target_clean) / 100.0
        
        # 2. Soundex phonetic matching
        soundex_match = 1.0 if jellyfish.soundex(input_clean) == jellyfish.soundex(target_clean) else 0.0
        
        # 3. Double Metaphone phonetic matching
        input_primary, input_secondary = self.dmetaphone(input_clean)
        target_primary, target_secondary = self.dmetaphone(target_clean)
        
        metaphone_match = 0.0
        if input_primary and target_primary:
            if (input_primary == target_primary or input_primary == target_secondary or
                input_secondary == target_primary or input_secondary == target_secondary):
                metaphone_match = 1.0
        
        # Weighted combination - emphasize phonetic for transcript errors
        # Character similarity: 40%, Soundex: 30%, Double Metaphone: 30%
        combined_score = (jaro_winkler_score * 0.4 + 
                         soundex_match * 0.3 + 
                         metaphone_match * 0.3)
        
        return combined_score * 100

    def _match_name_components(self, input_components: NameComponents, person_data: Dict[str, str]) -> Tuple[Dict[str, float], List[str]]:
        """Match name components against all patient fields"""
        component_scores = {}
        match_types = []
        
        first_name = person_data.get('name', '').strip()
        nickname = person_data.get('nickname', '').strip()  
        last_name = person_data.get('lastname', '').strip()
        
        # Always test input first_name against patient first_name and nickname fields in the data
        if input_components.first_name:
            best_score = max([
                self._calculate_similarity_score(input_components.first_name, first_name) if first_name else 0,
                self._calculate_similarity_score(input_components.first_name, nickname) if nickname else 0
            ])
            if best_score >= self.min_confidence:
                component_scores['first_name'] = best_score
                match_types.append('first_name')
        
        # Test input last_name against patient last_name (if different from first_name)
        if (input_components.last_name and last_name and 
            input_components.last_name != input_components.first_name):
            score = self._calculate_similarity_score(input_components.last_name, last_name)
            if score >= self.min_confidence:
                component_scores['last_name'] = score
                match_types.append('last_name')
        
        # Test input nickname against patient nickname (if different from first/last)
        if (input_components.nickname and nickname and
            input_components.nickname not in [input_components.first_name, input_components.last_name]):
            score = self._calculate_similarity_score(input_components.nickname, nickname)
            if score >= self.min_confidence:
                component_scores['nickname'] = score
                match_types.append('nickname')
        
        # Handle single name case: test against patient last_name too
        is_single_name = (input_components.first_name == input_components.last_name == input_components.nickname)
        if is_single_name and last_name and 'last_name' not in component_scores:
            score = self._calculate_similarity_score(input_components.first_name, last_name)
            if score >= self.min_confidence:
                component_scores['last_name'] = score
                match_types.append('last_name')
        
        return component_scores, match_types

    def _calculate_overall_confidence(self, component_scores: Dict[str, float], match_types: List[str], is_single_name: bool) -> float:
        """Calculate final confidence score from component scores - gives higher score for multiple component matches and first name matches"""
        if not component_scores:
            return 0.0
            
        if is_single_name:
            # For single names, use the best component score
            return max(component_scores.values())
        
        # Weighted average: first_name=60%, last_name=40%
        weights = {'first_name': 0.6, 'last_name': 0.4, 'nickname': 0.6}
        total_confidence = sum(component_scores.get(comp, 0) * weights.get(comp, 0) for comp in component_scores)
        total_weight = sum(weights.get(comp, 0) for comp in component_scores if comp in component_scores)
        
        overall_confidence = total_confidence / total_weight if total_weight > 0 else 0.0
        
        # Bonus for multiple component matches
        if len(match_types) > 1:
            overall_confidence = min(overall_confidence * 1.1, 100.0)
            
        return overall_confidence

    def _create_candidate(self, person_id: int, person_data: Dict[str, str], 
                         confidence_score: float, component_scores: Dict[str, float], 
                         match_types: List[str]) -> MatchCandidate:
        """Create a match candidate from scoring results"""
        # Create display name
        first_name = person_data.get('name', '').strip()
        last_name = person_data.get('lastname', '').strip()
        
        full_name_parts = []
        if first_name:
            full_name_parts.append(first_name)
        if last_name:
            full_name_parts.append(last_name)
        full_name = " ".join(full_name_parts) if full_name_parts else str(person_id)
        
        match_type = '+'.join(match_types) if match_types else 'low_confidence'
        
        return MatchCandidate(
            matched_id=person_id,
            matched_name=full_name,
            confidence_score=min(confidence_score, 100.0),
            component_scores=component_scores,
            match_type=match_type
        )

    def _process_results(self, all_candidates: List[MatchCandidate]) -> MatchResult:
        """Process and rank final results"""
        # Sort by confidence score
        all_candidates.sort(key=lambda x: x.confidence_score, reverse=True)
        
        # Take top 3 candidates
        top_candidates = all_candidates[:3]
        primary_match = top_candidates[0] if top_candidates else None
        
        # Check for ambiguous matches
        is_ambiguous = False
        if primary_match and len(top_candidates) > 1:
            for candidate in top_candidates[1:]:
                if (primary_match.confidence_score - candidate.confidence_score) <= self.ambiguity_threshold:
                    is_ambiguous = True
                    break
        
        return MatchResult(primary_match, top_candidates, is_ambiguous)

    def get_best_match(self, input_name: str, names_to_match: Dict[int, Dict[str, str]]) -> MatchResult:
        """
        Find the best match(es) for an input name using fuzzy matching across all fields
        """
        self.logger.debug(f"get_best_match: input='{input_name}', # candidates={len(names_to_match)}")
        
        if not input_name or not names_to_match:
            return MatchResult(None, [], False)
        
        # Tokenize input name
        input_components = self.tokenize_name(input_name)
        self.logger.debug(f"Tokenized input: {input_components}")
        
        all_candidates = []
        is_single_name = (input_components.first_name == input_components.last_name == input_components.nickname)
        
        # Evaluate each candidate
        for person_id, person_data in names_to_match.items():
            # Skip empty records
            if not any([person_data.get('name', '').strip(), 
                       person_data.get('nickname', '').strip(), 
                       person_data.get('lastname', '').strip()]):
                continue
            
            # Match using unified approach
            component_scores, match_types = self._match_name_components(input_components, person_data)
            
            # Calculate overall confidence
            overall_confidence = self._calculate_overall_confidence(component_scores, match_types, is_single_name)
            
            # Create candidate if valid match
            if component_scores and match_types and overall_confidence >= self.min_confidence:
                candidate = self._create_candidate(person_id, person_data, overall_confidence, component_scores, match_types)
                all_candidates.append(candidate)
        
        # Process and return results
        result = self._process_results(all_candidates)
        
        # Log results
        if result.primary_match:
            if len(result.all_candidates) > 1:
                self.logger.info(f"Name match for '{input_name}' - Top 3: " + 
                               ', '.join([f"#{i+1}: {c.matched_name} ({c.confidence_score:.1f}%)" 
                                        for i, c in enumerate(result.all_candidates)]))
                if result.is_ambiguous:
                    self.logger.debug(f"(!) Ambiguous match - using primary: {result.primary_match.matched_name}")
            else:
                self.logger.debug(f"Name match for '{input_name}': {result.primary_match.matched_name} ({result.primary_match.confidence_score:.1f}%)")
        else:
            self.logger.debug(f"No match found for '{input_name}'")
            
        return result


# Example usage and testing
def main():  
    logger = SpeakcareLogger(__name__)
    
    # Test data structure: {id: {name: first_name, nickname: nickname, lastname: last_name}}
    test_patients = {
        1: {"name": "John", "nickname": "Johnny", "lastname": "Smith"},
        2: {"name": "Jane", "nickname": "", "lastname": "Doe"}, 
        3: {"name": "William", "nickname": "Bill", "lastname": "Johnson"},
        4: {"name": "Elizabeth", "nickname": "Liz", "lastname": "Brown"},
        5: {"name": "Christopher", "nickname": "Chris", "lastname": "Wilson"},
        6: {"name": "Carol", "nickname": "", "lastname": "Smythe"},
        7: {"name": "Michael", "nickname": "", "lastname": "Johnson"},
        8: {"name": "Johnson", "nickname": "Bill", "lastname": "Williamson"},
    }

    matcher = NameMatcher(high_confidence_threshold=75, medium_confidence_threshold=55, min_confidence=35)
    
    # Test cases with assertions
    def assert_match(input_name: str, expected_id: int, expected_name: str, description: str):
        result = matcher.get_best_match(input_name, test_patients)
        assert result.primary_match is not None, f"Failed: {description} - No match found for '{input_name}'"
        assert result.primary_match.matched_id == expected_id, \
            f"Failed: {description} - Expected ID {expected_id}, got {result.primary_match.matched_id} for '{input_name}'"
        assert result.primary_match.matched_name == expected_name, \
            f"Failed: {description} - Expected '{expected_name}', got '{result.primary_match.matched_name}' for '{input_name}'"
        logger.info(f"✓ PASS: {description} - '{input_name}' correctly matched to '{expected_name}' (ID: {expected_id})")
    
    # Run assertions
    logger.info("Running name matching tests with assertions...")
    
    # Test exact nickname match
    assert_match("Johnny", 1, "John Smith", "Exact nickname match")
    
    # Test typo in nickname
    assert_match("Johny", 1, "John Smith", "Typo in nickname should still match")
    
    # Test shortened name
    assert_match("Jon", 1, "John Smith", "Shortened name should match")
    
    # Test full name match
    assert_match("Bill Johnson", 3, "William Johnson", "Full name with nickname should match")
    
    # Test partial/typo nickname
    assert_match("Bil", 3, "William Johnson", "Partial/typo nickname should match William")
    
    # Test nickname only match
    assert_match("Liz", 4, "Elizabeth Brown", "Nickname should match Elizabeth")
    
    # Test typo in first name
    assert_match("Elizabth", 4, "Elizabeth Brown", "Typo in first name should still match")
    
    # Test full name match
    assert_match("Chris Wilson", 5, "Christopher Wilson", "Full name should match")
    
    # Test phonetic last name match
    assert_match("Smyth", 6, "Carol Smythe", "Phonetic last name should match")
    
    # Test typo in first name
    assert_match("Michel", 7, "Michael Johnson", "Typo in first name should match")
    
    logger.info("✓ All tests passed successfully!")


if __name__ == "__main__":
    main()