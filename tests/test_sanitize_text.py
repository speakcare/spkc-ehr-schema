"""Tests for sanitize_text module."""

import sys
from pathlib import Path

# Add src to path for imports
#sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from schema_engine.sanitize_text import sanitize_for_json


class TestSanitizeForJson:
    """Test the sanitize_for_json function."""

    def test_double_quotes(self):
        """Test that double quotes are removed."""
        assert sanitize_for_json('If "yes" then proceed') == 'If yes then proceed'
        assert sanitize_for_json('Test ""input"" here') == 'Test input here'

    def test_single_quotes(self):
        """Test that single quotes are removed."""
        assert sanitize_for_json("It's working") == 'Its working'
        assert sanitize_for_json("'quoted' text") == 'quoted text'

    def test_backslashes(self):
        """Test that backslashes are replaced with spaces."""
        assert sanitize_for_json('Path\\to\\file') == 'Path to file'
        assert sanitize_for_json('Path\\\\to\\\\file') == 'Path to file'

    def test_control_characters(self):
        """Test that control characters (newlines, tabs) are removed."""
        assert sanitize_for_json('Line1\nLine2\tTabbed') == 'Line1 Line2 Tabbed'
        assert sanitize_for_json('Line1\nLine2\tTabbed\nLine3') == 'Line1 Line2 Tabbed Line3'
        assert sanitize_for_json('With\rCarriage') == 'With Carriage'

    def test_brackets_and_braces(self):
        """Test that brackets and braces are removed."""
        assert sanitize_for_json('Array[0] and {key}') == 'Array0 and key'
        assert sanitize_for_json('[bracketed] text') == 'bracketed text'
        assert sanitize_for_json('{braced} text') == 'braced text'

    def test_html_tags(self):
        """Test that HTML tags are removed."""
        assert sanitize_for_json('<b>Bold text</b>') == 'Bold text'
        assert sanitize_for_json('<i>Italic</i> text') == 'Italic text'
        assert sanitize_for_json('<span attr="value">Text</span>') == 'Text'

    def test_combined_cases(self):
        """Test multiple special characters in combination."""
        assert sanitize_for_json('<b>If "yes"</b> then [proceed]') == 'If yes then proceed'
        assert sanitize_for_json('<b>Bold "text"</b> with {braces}') == 'Bold text with braces'
        assert sanitize_for_json('"quote" and \\\\slashes') == 'quote and slashes'

    def test_non_strings(self):
        """Test that non-strings pass through unchanged."""
        assert sanitize_for_json(None) is None
        assert sanitize_for_json(123) == 123
        assert sanitize_for_json(123.45) == 123.45
        assert sanitize_for_json(True) is True
        assert sanitize_for_json(False) is False
        assert sanitize_for_json([1, 2, 3]) == [1, 2, 3]
        assert sanitize_for_json({'key': 'value'}) == {'key': 'value'}

    def test_real_world_example(self):
        """Test the actual problematic case from MHCS Nursing Daily Skilled Note."""
        problematic_text = 'If the answer to question 3 is "yes", what type of precautions are in place?'
        expected = 'If the answer to question 3 is yes, what type of precautions are in place?'
        assert sanitize_for_json(problematic_text) == expected

    def test_complex_case_with_parentheses(self):
        """Test complex case with multiple special characters, keeping parentheses."""
        complex_text = '<i>If the answer is "yes" (see [section] for details), proceed with {action}'
        expected = 'If the answer is yes (see section for details), proceed with action'
        assert sanitize_for_json(complex_text) == expected

    def test_empty_string(self):
        """Test that empty string remains empty."""
        assert sanitize_for_json('') == ''

    def test_only_special_characters(self):
        """Test string with only special characters."""
        # Note: <> are only removed when part of HTML tags, standalone they remain
        assert sanitize_for_json('"\\[]{}<>') == '<>'

    def test_whitespace_and_special_characters(self):
        """Test string with only whitespace and special characters."""
        assert sanitize_for_json('  "\\ \n\t[]{}  ') == ''

    def test_angle_brackets_html_tag_behavior(self):
        """Test that angle brackets are removed as part of HTML tag regex."""
        # The regex <[^>]+> will match everything from < to >
        assert sanitize_for_json('5 < 10 and 20 > 15') == '5 15'

    def test_unicode_characters(self):
        """Test that Unicode characters pass through."""
        assert sanitize_for_json('Café "café" with [brackets]') == 'Café café with brackets'
        assert sanitize_for_json('中文 "text" here') == '中文 text here'
        assert sanitize_for_json('Emoji 😀 "test"') == 'Emoji 😀 test'

    def test_very_long_string(self):
        """Test very long string with special characters."""
        long_text = 'Start ' + ('"' * 10) + ' middle ' + ('\\' * 10) + ' end'
        result = sanitize_for_json(long_text)
        assert '"' not in result
        assert result.count(' ') == 2  # Only the intentional spaces remain
        assert result == 'Start middle end'

    def test_parentheses_preserved(self):
        """Test that parentheses are preserved (not removed like brackets/braces)."""
        assert sanitize_for_json('Text (with parentheses) and [brackets]') == 'Text (with parentheses) and brackets'
        assert sanitize_for_json('(parentheses) {braces} [brackets]') == '(parentheses) braces brackets'

    def test_whitespace_normalization(self):
        """Test that multiple spaces are normalized to single space."""
        assert sanitize_for_json('Multiple    spaces    here') == 'Multiple spaces here'
        assert sanitize_for_json('   Leading and trailing   ') == 'Leading and trailing'
        assert sanitize_for_json('Tab\ttab\ttab') == 'Tab tab tab'

    def test_mixed_html_and_quotes(self):
        """Test HTML tags mixed with quotes."""
        assert sanitize_for_json('<p>"Paragraph" text</p>') == 'Paragraph text'
        assert sanitize_for_json('<div class="test">"Content"</div>') == 'Content'

    def test_nested_html_tags(self):
        """Test nested HTML tags."""
        assert sanitize_for_json('<div><span><b>Nested</b></span></div>') == 'Nested'
        assert sanitize_for_json('<p>Text <b>bold</b> text</p>') == 'Text bold text'

    def test_incomplete_html_tags(self):
        """Test behavior with incomplete or malformed HTML."""
        # The regex <[^>]+> matches anything from < to next >
        assert sanitize_for_json('<incomplete') == '<incomplete'  # No closing >, not matched
        assert sanitize_for_json('text < more text') == 'text < more text'  # No closing >, stays as is

    def test_all_special_chars_combined(self):
        """Test a string with all types of special characters."""
        text = '<b>Test</b> "quotes" \'single\' Path\\to\\file [array] {dict} Line1\nLine2'
        expected = 'Test quotes single Path to file array dict Line1 Line2'
        assert sanitize_for_json(text) == expected

    def test_consecutive_special_characters(self):
        """Test multiple consecutive special characters."""
        assert sanitize_for_json('"""') == ''
        assert sanitize_for_json('\\\\\\') == ''
        assert sanitize_for_json('[[[') == ''
        assert sanitize_for_json('{{{') == ''
        assert sanitize_for_json('"""\\\\\\[[[{{{') == ''

    def test_special_chars_with_actual_content(self):
        """Test that actual content is preserved when mixed with special chars."""
        assert sanitize_for_json('"Hello" "World"') == 'Hello World'
        assert sanitize_for_json('[Item1] [Item2]') == 'Item1 Item2'
        assert sanitize_for_json('{Key1} {Key2}') == 'Key1 Key2'

    def test_medical_text_examples(self):
        """Test real-world medical text examples."""
        text1 = 'Patient reports "pain" in [left] shoulder'
        assert sanitize_for_json(text1) == 'Patient reports pain in left shoulder'

        text2 = 'Assessment: <b>Condition improved</b> (see notes)'
        assert sanitize_for_json(text2) == 'Assessment: Condition improved (see notes)'

        text3 = 'Medications: {dose: 10mg}\nNotes: Patient\'s response is positive'
        assert sanitize_for_json(text3) == 'Medications: dose: 10mg Notes: Patients response is positive'

    def test_edge_case_only_html(self):
        """Test string that is only HTML tags."""
        assert sanitize_for_json('<div></div>') == ''
        assert sanitize_for_json('<br/>') == ''
        assert sanitize_for_json('<hr>') == ''

    def test_ampersands_and_special_entities(self):
        """Test that ampersands and HTML entities are handled."""
        # Ampersands are not removed by sanitize_for_json
        assert sanitize_for_json('Fish & Chips') == 'Fish & Chips'
        # HTML entities are not decoded, just tags are removed
        assert sanitize_for_json('&lt;tag&gt;') == '&lt;tag&gt;'

    def test_numbers_and_symbols(self):
        """Test that numbers and allowed symbols are preserved."""
        assert sanitize_for_json('Cost: $100.50') == 'Cost: $100.50'
        assert sanitize_for_json('Temperature: 98.6°F') == 'Temperature: 98.6°F'
        assert sanitize_for_json('Percentage: 50%') == 'Percentage: 50%'

    def test_url_like_strings(self):
        """Test URL-like strings (backslashes converted to spaces)."""
        # Note: backslashes become spaces
        assert sanitize_for_json('C:\\Users\\Documents\\file.txt') == 'C: Users Documents file.txt'
        # Forward slashes are preserved
        assert sanitize_for_json('http://example.com/path') == 'http://example.com/path'

    def test_semicolons_and_colons(self):
        """Test that semicolons and colons are preserved."""
        assert sanitize_for_json('Time: 10:30; Date: 2024-01-01') == 'Time: 10:30; Date: 2024-01-01'

    def test_hyphens_and_underscores(self):
        """Test that hyphens and underscores are preserved."""
        assert sanitize_for_json('patient_id: 123-456-789') == 'patient_id: 123-456-789'
        assert sanitize_for_json('multi-word-identifier') == 'multi-word-identifier'

    def test_empty_html_attributes(self):
        """Test HTML tags with empty or missing attributes."""
        assert sanitize_for_json('<div class="">Content</div>') == 'Content'
        assert sanitize_for_json('<img src="test.jpg">') == ''  # Self-closing tag, no content

    def test_script_and_style_tags(self):
        """Test that script and style tags are removed."""
        assert sanitize_for_json('<script>alert("test")</script>') == 'alert(test)'
        assert sanitize_for_json('<style>.class{color:red}</style>') == '.classcolor:red'

