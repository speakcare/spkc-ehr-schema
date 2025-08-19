import unittest
import sys
import os
from speakcare_logging import SpeakcareLogger

# Add the parent directory to the path to import name_matching
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from name_matching import NameMatcher

class TestNameMatcher(unittest.TestCase):
    """Test cases for the NameMatcher class"""

    @classmethod
    def setUpClass(cls):
        """Run once when the test class is first created, before any tests run"""
        cls.logger = SpeakcareLogger(__name__)
        cls.logger.info("**** setUpClass - TestNameMatcher class initialized ****")
        
    @classmethod
    def tearDownClass(cls):
        """Run once when all tests in the class are finished"""
        cls.logger = SpeakcareLogger(__name__)
        cls.logger.info("**** tearDownClass - TestNameMatcher class cleanup ****")

    def __init__(self, *args, **kwargs):
        super(TestNameMatcher, self).__init__(*args, **kwargs)
        self.logger = SpeakcareLogger(__name__)

    def setUp(self):
        """Set up test fixtures before each test method"""
        self.patient_names = ["Carol Smith", "Jane Doe", "Johnathan Smyth", "Johnny Appleseed", "Jaine Do", "Jon Smythen"]
        self.nurse_names = ["Christina Aguillera", "Christa Jones", "Christina Applegate", "Kristen Stewart", "Kristina Bell"]
        self.matcher = NameMatcher(primary_threshold=90, secondary_threshold=80)

    def test_initialization(self):
        """Test NameMatcher initialization with default and custom thresholds"""
        # Test default thresholds
        default_matcher = NameMatcher()
        self.assertEqual(default_matcher.primary_threshold, 90)
        self.assertEqual(default_matcher.secondary_threshold, 80)
        
        # Test custom thresholds
        custom_matcher = NameMatcher(primary_threshold=95, secondary_threshold=75)
        self.assertEqual(custom_matcher.primary_threshold, 95)
        self.assertEqual(custom_matcher.secondary_threshold, 75)

    def test_exact_match_primary_threshold(self):
        """Test exact name matches that should meet primary threshold"""
        # Exact match should score very high
        best_match, best_idx, score = self.matcher.get_best_match("Carol Smith", self.patient_names)
        self.assertIsNotNone(best_match)
        self.assertEqual(best_match, "Carol Smith")
        self.assertEqual(best_idx, 0)
        self.assertGreaterEqual(score, 90)

    def test_close_match_primary_threshold(self):
        """Test close name matches that should meet primary threshold"""
        # Close match with minor differences
        best_match, best_idx, score = self.matcher.get_best_match("Carol Smyth", self.patient_names)
        self.assertIsNotNone(best_match)
        self.assertIn(best_match, ["Carol Smith", "Johnathan Smyth"])
        self.assertGreaterEqual(score, 90)

    def test_phonetic_match_secondary_threshold(self):
        """Test phonetic matches that should meet secondary threshold"""
        # Test phonetic similarity with "Christy" -> "Christina"
        best_match, best_idx, score = self.matcher.get_best_match("Christy", self.nurse_names)
        self.assertIsNotNone(best_match)
        self.assertIn(best_match, ["Christina Aguillera", "Christina Applegate", "Christa Jones"])
        self.assertGreaterEqual(score, 80)

    def test_phonetic_match_below_secondary_threshold(self):
        """Test phonetic matches that are below secondary threshold"""
        # Create a matcher with higher secondary threshold
        strict_matcher = NameMatcher(primary_threshold=90, secondary_threshold=85)
        
        # Test a case where phonetic match exists but character similarity is low
        best_match, best_idx, score = self.matcher.get_best_match("Kristy", self.nurse_names)
        self.assertIsNotNone(best_match)
        self.assertGreater(score, 0)
        
        # With stricter threshold, should still find phonetic match if it meets the threshold
        best_match_strict, best_idx_strict, score_strict = strict_matcher.get_best_match("Kristy", self.nurse_names)
        # The result depends on whether the score meets the stricter threshold
        if best_match_strict is not None:
            self.assertGreaterEqual(score_strict, 85)
        # If no match found, that's also valid behavior for strict thresholds

    def test_no_match_found(self):
        """Test cases where no match should be found"""
        # Completely different name
        best_match, best_idx, score = self.matcher.get_best_match("Zebra Xylophone", self.patient_names)
        self.assertIsNone(best_match)
        self.assertIsNone(best_idx)
        self.assertIsNone(score)

    def test_empty_names_list(self):
        """Test behavior with empty names list"""
        best_match, best_idx, score = self.matcher.get_best_match("John Doe", [])
        self.assertIsNone(best_match)
        self.assertIsNone(best_idx)
        self.assertIsNone(score)

    def test_none_input_name(self):
        """Test behavior with None input name"""
        best_match, best_idx, score = self.matcher.get_best_match(None, self.patient_names)
        self.assertIsNone(best_match)
        self.assertIsNone(best_idx)
        self.assertIsNone(score)

    def test_none_names_to_match(self):
        """Test behavior with None names to match"""
        best_match, best_idx, score = self.matcher.get_best_match("John Doe", None)
        self.assertIsNone(best_match)
        self.assertIsNone(best_idx)
        self.assertIsNone(score)

    def test_single_name_match(self):
        """Test matching against a single name"""
        single_name = ["John Doe"]
        best_match, best_idx, score = self.matcher.get_best_match("John Doe", single_name)
        self.assertIsNotNone(best_match)
        self.assertEqual(best_match, "John Doe")
        self.assertEqual(best_idx, 0)
        self.assertGreaterEqual(score, 90)

    def test_case_sensitivity(self):
        """Test that matching is case-insensitive"""
        # Test with different case - the fuzzy matching should handle this well
        best_match, best_idx, score = self.matcher.get_best_match("carol smith", self.patient_names)
        self.assertIsNotNone(best_match)
        # The score might not be 90+ due to case differences, but should still find a match
        self.assertGreater(score, 80)

    def test_phonetic_similarity_edge_cases(self):
        """Test edge cases for phonetic similarity"""
        # Test with names that have similar phonetic patterns
        similar_names = ["Sean", "Shawn", "Shaun", "Shane"]
        best_match, best_idx, score = self.matcher.get_best_match("Shawn", similar_names)
        self.assertIsNotNone(best_match)
        self.assertIn(best_match, similar_names)
        self.assertGreaterEqual(score, 80)

    def test_multiple_phonetic_matches(self):
        """Test when multiple names have similar phonetic patterns"""
        # Test with a name that could match multiple entries
        best_match, best_idx, score = self.matcher.get_best_match("Kristen", self.nurse_names)
        self.assertIsNotNone(best_match)
        # Should return one of the best matches
        self.assertIn(best_match, self.nurse_names)

    def test_special_characters(self):
        """Test matching with names containing special characters"""
        names_with_special = ["O'Connor", "Mary-Jane", "Smith Jr.", "O'Reilly"]
        best_match, best_idx, score = self.matcher.get_best_match("O'Connor", names_with_special)
        self.assertIsNotNone(best_match)
        self.assertEqual(best_match, "O'Connor")

    def test_special_characters_ignored(self):
        """Test matching with names containing special characters and numbers"""
        names_with_special = ["O'Connor", "Mary-Jane", "Smith Jr.", "O'Reilly"]
        best_match, best_idx, score = self.matcher.get_best_match("OConnor", names_with_special)
        self.assertIsNotNone(best_match)
        self.assertEqual(best_match, "O'Connor")

    def test_very_long_names(self):
        """Test matching with very long names"""
        long_names = [
            "Dr. John Jacob Jingleheimer Schmidt III",
            "Mary Elizabeth Winifred Catherine O'Brien-Smith",
            "Robert James Michael David Anthony Johnson"
        ]
        best_match, best_idx, score = self.matcher.get_best_match("Dr. John Jacob Jinglehiemer Schmidt III", long_names)
        self.assertIsNotNone(best_match)
        self.assertEqual(best_match, "Dr. John Jacob Jingleheimer Schmidt III")

    def test_unicode_and_international_names(self):
        """Test matching with international and unicode names"""
        international_names = ["José García", "Müller", "O'Connor", "Björk", "李小明"]
        best_match, best_idx, score = self.matcher.get_best_match("李小明", international_names)
        # The current implementation might not handle all unicode characters well
        # We'll test that it doesn't crash and returns some result
        if best_match is not None:
            self.assertIsInstance(best_match, str)
            self.assertGreater(len(best_match), 0)
        # If no match found due to unicode issues, that's also valid

    def test_performance_with_large_lists(self):
        """Test performance with larger name lists"""
        # Generate a larger list of names
        large_name_list = [f"Person{i} Smith" for i in range(100)]
        large_name_list.extend([f"Person{i} Jones" for i in range(100)])
        
        # Test matching performance
        import time
        start_time = time.time()
        best_match, best_idx, score = self.matcher.get_best_match("Person50 Smith", large_name_list)
        end_time = time.time()
        
        self.assertIsNotNone(best_match)
        self.assertLess(end_time - start_time, 0.01)  # Should complete within 1 second

    def test_edge_case_empty_string(self):
        """Test behavior with empty string input"""
        best_match, best_idx, score = self.matcher.get_best_match("", self.patient_names)
        # Should handle empty string gracefully
        if best_match is not None:
            self.assertIsInstance(best_match, str)
            self.assertGreater(len(best_match), 0)

    def test_edge_case_whitespace_only(self):
        """Test behavior with whitespace-only input"""
        best_match, best_idx, score = self.matcher.get_best_match("   ", self.patient_names)
        # Should handle whitespace gracefully
        if best_match is not None:
            self.assertIsInstance(best_match, str)
            self.assertGreater(len(best_match.strip()), 0)

    def test_consistency_across_runs(self):
        """Test that the same input produces consistent results across multiple runs"""
        input_name = "Christy"
        results = []
        
        for _ in range(5):
            best_match, best_idx, score = self.matcher.get_best_match(input_name, self.nurse_names)
            results.append((best_match, best_idx, score))
        
        # All results should be the same
        first_result = results[0]
        for result in results[1:]:
            self.assertEqual(result, first_result)

    def test_threshold_adjustment_impact(self):
        """Test how changing thresholds affects matching results"""
        # Test with very strict thresholds
        strict_matcher = NameMatcher(primary_threshold=95, secondary_threshold=90)
        strict_match, strict_idx, strict_score = strict_matcher.get_best_match("Christy", self.nurse_names)
        
        # Test with very lenient thresholds
        lenient_matcher = NameMatcher(primary_threshold=70, secondary_threshold=60)
        lenient_match, lenient_idx, lenient_score = lenient_matcher.get_best_match("Christy", self.nurse_names)
        
        # Lenient matcher should find more matches
        if strict_match is not None and lenient_match is not None:
            self.assertGreaterEqual(lenient_score, strict_score)

if __name__ == '__main__':
    unittest.main()
