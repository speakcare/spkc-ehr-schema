import unittest
from speakcare_logging import SpeakcareLogger
from name_matching import NameMatcher


class TestNameMatching(unittest.TestCase):
    """Test cases for the NameMatcher class"""
    
    def setUp(self):
        """Set up test fixtures before each test method."""
        self.logger = SpeakcareLogger(__name__)
        
        # Test data structure: {id: {name: first_name, nickname: nickname, lastname: last_name}}
        self.test_patients = {
            1: {"name": "John", "nickname": "Johnny", "lastname": "Smith"},
            2: {"name": "Jane", "nickname": "", "lastname": "Doe"}, 
            3: {"name": "William", "nickname": "Bill", "lastname": "Johnson"},
            4: {"name": "Elizabeth", "nickname": "Liz", "lastname": "Brown"},
            5: {"name": "Christopher", "nickname": "Chris", "lastname": "Wilson"},
            6: {"name": "Carol", "nickname": "", "lastname": "Smythe"},
            7: {"name": "Michael", "nickname": "", "lastname": "Johnson"},
            8: {"name": "Johnson", "nickname": "Bill", "lastname": "Williamson"},
        }

        self.matcher = NameMatcher(high_confidence_threshold=75, medium_confidence_threshold=55, min_confidence=35)
    
    def test_exact_nickname_match(self):
        """Test exact nickname match"""
        result = self.matcher.get_best_match("Johnny", self.test_patients)
        self.assertIsNotNone(result.primary_match, "No match found for 'Johnny'")
        self.assertEqual(result.primary_match.matched_id, 1, "Expected ID 1 for 'Johnny'")
        self.assertEqual(result.primary_match.matched_name, "John Smith", "Expected 'John Smith' for 'Johnny'")
        self.logger.info("✓ PASS: Exact nickname match - 'Johnny' correctly matched to 'John Smith' (ID: 1)")
    
    def test_typo_in_nickname(self):
        """Test typo in nickname should still match"""
        result = self.matcher.get_best_match("Johny", self.test_patients)
        self.assertIsNotNone(result.primary_match, "No match found for 'Johny'")
        self.assertEqual(result.primary_match.matched_id, 1, "Expected ID 1 for 'Johny'")
        self.assertEqual(result.primary_match.matched_name, "John Smith", "Expected 'John Smith' for 'Johny'")
        self.logger.info("✓ PASS: Typo in nickname - 'Johny' correctly matched to 'John Smith' (ID: 1)")
    
    def test_shortened_name(self):
        """Test shortened name should match"""
        result = self.matcher.get_best_match("Jon", self.test_patients)
        self.assertIsNotNone(result.primary_match, "No match found for 'Jon'")
        self.assertEqual(result.primary_match.matched_id, 1, "Expected ID 1 for 'Jon'")
        self.assertEqual(result.primary_match.matched_name, "John Smith", "Expected 'John Smith' for 'Jon'")
        self.logger.info("✓ PASS: Shortened name - 'Jon' correctly matched to 'John Smith' (ID: 1)")
    
    def test_full_name_with_nickname(self):
        """Test full name with nickname should match"""
        result = self.matcher.get_best_match("Bill Johnson", self.test_patients)
        self.assertIsNotNone(result.primary_match, "No match found for 'Bill Johnson'")
        self.assertEqual(result.primary_match.matched_id, 3, "Expected ID 3 for 'Bill Johnson'")
        self.assertEqual(result.primary_match.matched_name, "William Johnson", "Expected 'William Johnson' for 'Bill Johnson'")
        self.logger.info("✓ PASS: Full name with nickname - 'Bill Johnson' correctly matched to 'William Johnson' (ID: 3)")
    
    def test_partial_typo_nickname(self):
        """Test partial/typo nickname should match William"""
        result = self.matcher.get_best_match("Bil", self.test_patients)
        self.assertIsNotNone(result.primary_match, "No match found for 'Bil'")
        self.assertEqual(result.primary_match.matched_id, 3, "Expected ID 3 for 'Bil'")
        self.assertEqual(result.primary_match.matched_name, "William Johnson", "Expected 'William Johnson' for 'Bil'")
        self.logger.info("✓ PASS: Partial/typo nickname - 'Bil' correctly matched to 'William Johnson' (ID: 3)")
    
    def test_nickname_only_match(self):
        """Test nickname should match Elizabeth"""
        result = self.matcher.get_best_match("Liz", self.test_patients)
        self.assertIsNotNone(result.primary_match, "No match found for 'Liz'")
        self.assertEqual(result.primary_match.matched_id, 4, "Expected ID 4 for 'Liz'")
        self.assertEqual(result.primary_match.matched_name, "Elizabeth Brown", "Expected 'Elizabeth Brown' for 'Liz'")
        self.logger.info("✓ PASS: Nickname only match - 'Liz' correctly matched to 'Elizabeth Brown' (ID: 4)")
    
    def test_typo_in_first_name(self):
        """Test typo in first name should still match"""
        result = self.matcher.get_best_match("Elizabth", self.test_patients)
        self.assertIsNotNone(result.primary_match, "No match found for 'Elizabth'")
        self.assertEqual(result.primary_match.matched_id, 4, "Expected ID 4 for 'Elizabth'")
        self.assertEqual(result.primary_match.matched_name, "Elizabeth Brown", "Expected 'Elizabeth Brown' for 'Elizabth'")
        self.logger.info("✓ PASS: Typo in first name - 'Elizabth' correctly matched to 'Elizabeth Brown' (ID: 4)")
    
    def test_full_name_match(self):
        """Test full name should match"""
        result = self.matcher.get_best_match("Chris Wilson", self.test_patients)
        self.assertIsNotNone(result.primary_match, "No match found for 'Chris Wilson'")
        self.assertEqual(result.primary_match.matched_id, 5, "Expected ID 5 for 'Chris Wilson'")
        self.assertEqual(result.primary_match.matched_name, "Christopher Wilson", "Expected 'Christopher Wilson' for 'Chris Wilson'")
        self.logger.info("✓ PASS: Full name match - 'Chris Wilson' correctly matched to 'Christopher Wilson' (ID: 5)")
    
    def test_phonetic_last_name_match(self):
        """Test phonetic last name should match"""
        result = self.matcher.get_best_match("Smyth", self.test_patients)
        self.assertIsNotNone(result.primary_match, "No match found for 'Smyth'")
        self.assertEqual(result.primary_match.matched_id, 6, "Expected ID 6 for 'Smyth'")
        self.assertEqual(result.primary_match.matched_name, "Carol Smythe", "Expected 'Carol Smythe' for 'Smyth'")
        self.logger.info("✓ PASS: Phonetic last name match - 'Smyth' correctly matched to 'Carol Smythe' (ID: 6)")
    
    def test_typo_in_first_name_michael(self):
        """Test typo in first name should match Michael"""
        result = self.matcher.get_best_match("Michel", self.test_patients)
        self.assertIsNotNone(result.primary_match, "No match found for 'Michel'")
        self.assertEqual(result.primary_match.matched_id, 7, "Expected ID 7 for 'Michel'")
        self.assertEqual(result.primary_match.matched_name, "Michael Johnson", "Expected 'Michael Johnson' for 'Michel'")
        self.logger.info("✓ PASS: Typo in first name - 'Michel' correctly matched to 'Michael Johnson' (ID: 7)")


if __name__ == "__main__":
    unittest.main()
