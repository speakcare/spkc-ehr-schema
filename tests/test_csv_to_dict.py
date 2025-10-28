import pytest
import tempfile
import os
from pathlib import Path
import sys

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from csv_to_dict import (
    read_key_value_csv_path,
    read_key_value_csv_stream,
)


def create_temp_csv(content: str) -> str:
    """Helper to create a temporary CSV file and return its path."""
    fd, path = tempfile.mkstemp(suffix=".csv", text=True)
    try:
        with os.fdopen(fd, "w") as f:
            f.write(content)
    except Exception:
        os.close(fd)
        raise
    return path


class TestBasicFunctionality:
    """Test basic CSV to dict conversion."""

    def test_simple_conversion(self):
        """Test basic conversion with 5 columns, using 2nd as key and 5th as value."""
        csv_content = """Col1,KeyColumn,Col3,Col4,ValueColumn
data1,key1,data3,data4,value1
data2,key2,data3,data4,value2
data3,key3,data3,data4,value3"""

        path = create_temp_csv(csv_content)
        try:
            result = read_key_value_csv_path(
                path, key_col="KeyColumn", value_col="ValueColumn"
            )
            assert result == {
                "key1": "value1",
                "key2": "value2",
                "key3": "value3",
            }
        finally:
            os.unlink(path)

    def test_with_empty_keys(self):
        """Test that empty keys are skipped by default."""
        csv_content = """Col1,KeyColumn,Col3,Col4,ValueColumn
data1,key1,data3,data4,value1
data2,,data3,data4,value2
data3,  ,data3,data4,value3
data4,key4,data3,data4,value4"""

        path = create_temp_csv(csv_content)
        try:
            result = read_key_value_csv_path(
                path, key_col="KeyColumn", value_col="ValueColumn"
            )
            # Empty and whitespace-only keys should be skipped
            assert result == {
                "key1": "value1",
                "key4": "value4",
            }
        finally:
            os.unlink(path)

    def test_with_empty_keys_not_skipped(self):
        """Test that empty keys are included when skip_blank_keys=False."""
        csv_content = """Col1,KeyColumn,Col3,Col4,ValueColumn
data1,key1,data3,data4,value1
data2,,data3,data4,value2
data3,key3,data3,data4,value3"""

        path = create_temp_csv(csv_content)
        try:
            result = read_key_value_csv_path(
                path,
                key_col="KeyColumn",
                value_col="ValueColumn",
                skip_blank_keys=False,
            )
            assert result == {
                "key1": "value1",
                "": "value2",
                "key3": "value3",
            }
        finally:
            os.unlink(path)


class TestKeyPrefix:
    """Test key_prefix parameter."""

    def test_key_prefix_basic(self):
        """Test that key_prefix adds prefix to keys."""
        csv_content = """Col1,KeyColumn,Col3,Col4,ValueColumn
data1,name,data3,data4,John
data2,age,data3,data4,30
data3,city,data3,data4,NYC"""

        path = create_temp_csv(csv_content)
        try:
            result = read_key_value_csv_path(
                path,
                key_col="KeyColumn",
                value_col="ValueColumn",
                key_prefix="patient",
            )
            assert result == {
                "patient_name": "John",
                "patient_age": "30",
                "patient_city": "NYC",
            }
        finally:
            os.unlink(path)

    def test_key_prefix_already_present(self):
        """Test that keys already with prefix are not double-prefixed."""
        csv_content = """Col1,KeyColumn,Col3,Col4,ValueColumn
data1,patient_name,data3,data4,John
data2,age,data3,data4,30
data3,patient_city,data3,data4,NYC"""

        path = create_temp_csv(csv_content)
        try:
            result = read_key_value_csv_path(
                path,
                key_col="KeyColumn",
                value_col="ValueColumn",
                key_prefix="patient",
            )
            # Keys already with prefix should not be double-prefixed
            assert result == {
                "patient_name": "John",
                "patient_age": "30",
                "patient_city": "NYC",
            }
        finally:
            os.unlink(path)

    def test_key_prefix_none(self):
        """Test that key_prefix=None doesn't modify keys."""
        csv_content = """Col1,KeyColumn,Col3,Col4,ValueColumn
data1,name,data3,data4,John
data2,age,data3,data4,30"""

        path = create_temp_csv(csv_content)
        try:
            result = read_key_value_csv_path(
                path,
                key_col="KeyColumn",
                value_col="ValueColumn",
                key_prefix=None,
            )
            assert result == {
                "name": "John",
                "age": "30",
            }
        finally:
            os.unlink(path)

    def test_key_prefix_mixed_with_empty_keys(self):
        """Test key_prefix with empty keys (should skip empty keys)."""
        csv_content = """Col1,KeyColumn,Col3,Col4,ValueColumn
data1,name,data3,data4,John
data2,,data3,data4,ignored
data3,patient_age,data3,data4,30"""

        path = create_temp_csv(csv_content)
        try:
            result = read_key_value_csv_path(
                path,
                key_col="KeyColumn",
                value_col="ValueColumn",
                key_prefix="patient",
            )
            assert result == {
                "patient_name": "John",
                "patient_age": "30",
            }
        finally:
            os.unlink(path)


class TestDuplicatePolicies:
    """Test all duplicate key handling policies."""

    def test_duplicate_policy_last(self):
        """Test that 'last' policy keeps the last value."""
        csv_content = """Col1,KeyColumn,Col3,Col4,ValueColumn
data1,key1,data3,data4,first_value
data2,key2,data3,data4,value2
data3,key1,data3,data4,last_value"""

        path = create_temp_csv(csv_content)
        try:
            result = read_key_value_csv_path(
                path,
                key_col="KeyColumn",
                value_col="ValueColumn",
                on_duplicate="last",
            )
            assert result == {
                "key1": "last_value",
                "key2": "value2",
            }
        finally:
            os.unlink(path)

    def test_duplicate_policy_first(self):
        """Test that 'first' policy keeps the first value."""
        csv_content = """Col1,KeyColumn,Col3,Col4,ValueColumn
data1,key1,data3,data4,first_value
data2,key2,data3,data4,value2
data3,key1,data3,data4,last_value"""

        path = create_temp_csv(csv_content)
        try:
            result = read_key_value_csv_path(
                path,
                key_col="KeyColumn",
                value_col="ValueColumn",
                on_duplicate="first",
            )
            assert result == {
                "key1": "first_value",
                "key2": "value2",
            }
        finally:
            os.unlink(path)

    def test_duplicate_policy_error(self):
        """Test that 'error' policy raises on duplicate keys."""
        csv_content = """Col1,KeyColumn,Col3,Col4,ValueColumn
data1,key1,data3,data4,first_value
data2,key2,data3,data4,value2
data3,key1,data3,data4,last_value"""

        path = create_temp_csv(csv_content)
        try:
            with pytest.raises(ValueError, match="Duplicate key 'key1'"):
                read_key_value_csv_path(
                    path,
                    key_col="KeyColumn",
                    value_col="ValueColumn",
                    on_duplicate="error",
                )
        finally:
            os.unlink(path)

    def test_duplicate_policy_concat(self):
        """Test that 'concat' policy concatenates values."""
        csv_content = """Col1,KeyColumn,Col3,Col4,ValueColumn
data1,key1,data3,data4,first_value
data2,key2,data3,data4,value2
data3,key1,data3,data4,second_value
data4,key1,data3,data4,third_value"""

        path = create_temp_csv(csv_content)
        try:
            result = read_key_value_csv_path(
                path,
                key_col="KeyColumn",
                value_col="ValueColumn",
                on_duplicate="concat",
                concat_sep=". ",
            )
            assert result == {
                "key1": "first_value. second_value. third_value",
                "key2": "value2",
            }
        finally:
            os.unlink(path)

    def test_duplicate_policy_concat_custom_separator(self):
        """Test concat with custom separator."""
        csv_content = """Col1,KeyColumn,Col3,Col4,ValueColumn
data1,key1,data3,data4,A
data2,key1,data3,data4,B
data3,key1,data3,data4,C"""

        path = create_temp_csv(csv_content)
        try:
            result = read_key_value_csv_path(
                path,
                key_col="KeyColumn",
                value_col="ValueColumn",
                on_duplicate="concat",
                concat_sep=", ",
            )
            assert result == {
                "key1": "A, B, C",
            }
        finally:
            os.unlink(path)

    def test_duplicate_policy_with_key_prefix(self):
        """Test duplicate handling with key_prefix."""
        csv_content = """Col1,KeyColumn,Col3,Col4,ValueColumn
data1,name,data3,data4,John
data2,patient_name,data3,data4,Jane
data3,age,data3,data4,30"""

        path = create_temp_csv(csv_content)
        try:
            # Both 'name' and 'patient_name' become 'patient_name' after prefixing
            result = read_key_value_csv_path(
                path,
                key_col="KeyColumn",
                value_col="ValueColumn",
                key_prefix="patient",
                on_duplicate="last",
            )
            assert result == {
                "patient_name": "Jane",  # Last value wins
                "patient_age": "30",
            }
        finally:
            os.unlink(path)


class TestNegativeCases:
    """Test error conditions."""

    def test_missing_key_column(self):
        """Test that missing key column raises KeyError."""
        csv_content = """Col1,KeyColumn,Col3,Col4,ValueColumn
data1,key1,data3,data4,value1"""

        path = create_temp_csv(csv_content)
        try:
            with pytest.raises(KeyError, match="Column 'MissingKey' not found"):
                read_key_value_csv_path(
                    path, key_col="MissingKey", value_col="ValueColumn"
                )
        finally:
            os.unlink(path)

    def test_missing_value_column(self):
        """Test that missing value column raises KeyError."""
        csv_content = """Col1,KeyColumn,Col3,Col4,ValueColumn
data1,key1,data3,data4,value1"""

        path = create_temp_csv(csv_content)
        try:
            with pytest.raises(KeyError, match="Column 'MissingValue' not found"):
                read_key_value_csv_path(
                    path, key_col="KeyColumn", value_col="MissingValue"
                )
        finally:
            os.unlink(path)

    def test_empty_csv(self):
        """Test that CSV with no header raises error."""
        csv_content = ""

        path = create_temp_csv(csv_content)
        try:
            with pytest.raises(ValueError, match="no header row"):
                read_key_value_csv_path(
                    path, key_col="KeyColumn", value_col="ValueColumn"
                )
        finally:
            os.unlink(path)

    def test_invalid_duplicate_policy(self):
        """Test that invalid duplicate policy raises error."""
        csv_content = """Col1,KeyColumn,Col3,Col4,ValueColumn
data1,key1,data3,data4,value1"""

        path = create_temp_csv(csv_content)
        try:
            with pytest.raises(ValueError, match="Unknown on_duplicate policy"):
                read_key_value_csv_path(
                    path,
                    key_col="KeyColumn",
                    value_col="ValueColumn",
                    on_duplicate="invalid",  # type: ignore
                )
        finally:
            os.unlink(path)

    def test_case_insensitive_column_not_found(self):
        """Test case-insensitive column lookup with missing column."""
        csv_content = """Col1,KeyColumn,Col3,Col4,ValueColumn
data1,key1,data3,data4,value1"""

        path = create_temp_csv(csv_content)
        try:
            with pytest.raises(
                KeyError, match="Column 'MissingKey' \\(case-insensitive\\) not found"
            ):
                read_key_value_csv_path(
                    path,
                    key_col="MissingKey",
                    value_col="ValueColumn",
                    case_insensitive=True,
                )
        finally:
            os.unlink(path)


class TestCaseInsensitive:
    """Test case-insensitive column matching."""

    def test_case_insensitive_headers(self):
        """Test that case-insensitive matching works."""
        csv_content = """Col1,KeyColumn,Col3,Col4,ValueColumn
data1,key1,data3,data4,value1
data2,key2,data3,data4,value2"""

        path = create_temp_csv(csv_content)
        try:
            # Use lowercase column names with case_insensitive=True
            result = read_key_value_csv_path(
                path,
                key_col="keycolumn",
                value_col="valuecolumn",
                case_insensitive=True,
            )
            assert result == {
                "key1": "value1",
                "key2": "value2",
            }
        finally:
            os.unlink(path)


class TestWhitespace:
    """Test whitespace handling."""

    def test_strip_whitespace_enabled(self):
        """Test that whitespace is stripped by default."""
        csv_content = """Col1,KeyColumn,Col3,Col4,ValueColumn
data1,  key1  ,data3,data4,  value1  
data2,key2,data3,data4,value2"""

        path = create_temp_csv(csv_content)
        try:
            result = read_key_value_csv_path(
                path, key_col="KeyColumn", value_col="ValueColumn"
            )
            assert result == {
                "key1": "value1",
                "key2": "value2",
            }
        finally:
            os.unlink(path)

    def test_strip_whitespace_disabled(self):
        """Test that whitespace is preserved when strip_whitespace=False."""
        csv_content = """Col1,KeyColumn,Col3,Col4,ValueColumn
data1,"  key1  ",data3,data4,value1
data2,key2,data3,data4,value2"""

        path = create_temp_csv(csv_content)
        try:
            result = read_key_value_csv_path(
                path,
                key_col="KeyColumn",
                value_col="ValueColumn",
                strip_whitespace=False,
            )
            # Note: CSV parser preserves quoted whitespace in KeyColumn but
            # unquoted fields have natural behavior
            assert result == {
                "  key1  ": "value1",
                "key2": "value2",
            }
        finally:
            os.unlink(path)


class TestStreamInterface:
    """Test the stream interface directly."""

    def test_read_from_stream(self):
        """Test reading from a stream instead of file path."""
        csv_content = """Col1,KeyColumn,Col3,Col4,ValueColumn
data1,key1,data3,data4,value1
data2,key2,data3,data4,value2"""

        path = create_temp_csv(csv_content)
        try:
            with open(path, "r", encoding="utf-8-sig", newline="") as f:
                result = read_key_value_csv_stream(
                    f, key_col="KeyColumn", value_col="ValueColumn"
                )
            assert result == {
                "key1": "value1",
                "key2": "value2",
            }
        finally:
            os.unlink(path)

    def test_stream_with_key_prefix(self):
        """Test stream interface with key_prefix."""
        csv_content = """Col1,KeyColumn,Col3,Col4,ValueColumn
data1,name,data3,data4,John
data2,patient_age,data3,data4,30"""

        path = create_temp_csv(csv_content)
        try:
            with open(path, "r", encoding="utf-8-sig", newline="") as f:
                result = read_key_value_csv_stream(
                    f,
                    key_col="KeyColumn",
                    value_col="ValueColumn",
                    key_prefix="patient",
                )
            assert result == {
                "patient_name": "John",
                "patient_age": "30",
            }
        finally:
            os.unlink(path)


class TestComplexScenarios:
    """Test complex real-world scenarios."""

    def test_comprehensive_scenario(self):
        """Test a comprehensive scenario with multiple features."""
        csv_content = """ID,FieldName,Type,Required,Description
1,first_name,string,yes,Patient first name
2,patient_last_name,string,yes,Patient last name
3,,string,no,This row should be skipped
4,age,integer,yes,Patient age
5,first_name,string,yes,Duplicate - should concat
6,address,string,no,Patient address"""

        path = create_temp_csv(csv_content)
        try:
            result = read_key_value_csv_path(
                path,
                key_col="FieldName",
                value_col="Description",
                key_prefix="patient",
                on_duplicate="concat",
                concat_sep=" | ",
            )
            assert result == {
                "patient_first_name": "Patient first name | Duplicate - should concat",
                "patient_last_name": "Patient last name",
                "patient_age": "Patient age",
                "patient_address": "Patient address",
            }
        finally:
            os.unlink(path)


class TestSanitization:
    """Test value sanitization."""

    def test_sanitize_values_basic(self):
        """Test basic sanitization of values."""
        csv_content = """Col1,KeyColumn,Col3,Col4,ValueColumn
data1,key1,data3,data4,If "yes" then proceed
data2,key2,data3,data4,Path\\to\\file
data3,key3,data3,data4,<b>Bold text</b>"""

        path = create_temp_csv(csv_content)
        try:
            result = read_key_value_csv_path(
                path,
                key_col="KeyColumn",
                value_col="ValueColumn",
                sanitize_values=True,
            )
            assert result == {
                "key1": "If yes then proceed",
                "key2": "Path to file",
                "key3": "Bold text",
            }
        finally:
            os.unlink(path)

    def test_sanitize_values_disabled(self):
        """Test that sanitization can be disabled."""
        csv_content = """Col1,KeyColumn,Col3,Col4,ValueColumn
data1,key1,data3,data4,If "yes" then proceed
data2,key2,data3,data4,<b>Bold text</b>"""

        path = create_temp_csv(csv_content)
        try:
            result = read_key_value_csv_path(
                path,
                key_col="KeyColumn",
                value_col="ValueColumn",
                sanitize_values=False,
            )
            # Values should not be sanitized
            assert result == {
                "key1": 'If "yes" then proceed',
                "key2": "<b>Bold text</b>",
            }
        finally:
            os.unlink(path)

    def test_sanitize_html_tags(self):
        """Test that HTML tags are removed from values."""
        csv_content = """Col1,KeyColumn,Col3,Col4,ValueColumn
data1,question1,data3,data4,<b>Assessment</b> complete
data2,question2,data3,data4,<i>Review</i> the <span>notes</span>
data3,question3,data3,data4,<div>Multiple</div> <p>tags</p>"""

        path = create_temp_csv(csv_content)
        try:
            result = read_key_value_csv_path(
                path,
                key_col="KeyColumn",
                value_col="ValueColumn",
                sanitize_values=True,
            )
            assert result == {
                "question1": "Assessment complete",
                "question2": "Review the notes",
                "question3": "Multiple tags",
            }
        finally:
            os.unlink(path)

    def test_sanitize_quotes_and_backslashes(self):
        """Test that quotes and backslashes are sanitized."""
        csv_content = """Col1,KeyColumn,Col3,Col4,ValueColumn
data1,q1,data3,data4,If "yes" proceed
data2,q2,data3,data4,It's working
data3,q3,data3,data4,Path\\to\\file"""

        path = create_temp_csv(csv_content)
        try:
            result = read_key_value_csv_path(
                path,
                key_col="KeyColumn",
                value_col="ValueColumn",
                sanitize_values=True,
            )
            assert result == {
                "q1": "If yes proceed",
                "q2": "Its working",
                "q3": "Path to file",
            }
        finally:
            os.unlink(path)

    def test_sanitize_brackets_and_braces(self):
        """Test that brackets and braces are removed."""
        csv_content = """Col1,KeyColumn,Col3,Col4,ValueColumn
data1,q1,data3,data4,Array[0] value
data2,q2,data3,data4,Object {key} value
data3,q3,data3,data4,[Bracketed] and {braced}"""

        path = create_temp_csv(csv_content)
        try:
            result = read_key_value_csv_path(
                path,
                key_col="KeyColumn",
                value_col="ValueColumn",
                sanitize_values=True,
            )
            assert result == {
                "q1": "Array0 value",
                "q2": "Object key value",
                "q3": "Bracketed and braced",
            }
        finally:
            os.unlink(path)

    def test_sanitize_control_characters(self):
        """Test that control characters (newlines, tabs) are removed."""
        csv_content = """Col1,KeyColumn,Col3,Col4,ValueColumn
data1,q1,data3,data4,"Line1
Line2	Tabbed"
data2,q2,data3,data4,Text with newline character"""

        path = create_temp_csv(csv_content)
        try:
            result = read_key_value_csv_path(
                path,
                key_col="KeyColumn",
                value_col="ValueColumn",
                sanitize_values=True,
            )
            assert result == {
                "q1": "Line1 Line2 Tabbed",
                "q2": "Text with newline character",
            }
        finally:
            os.unlink(path)

    def test_sanitize_with_key_prefix(self):
        """Test sanitization combined with key_prefix."""
        csv_content = """Col1,KeyColumn,Col3,Col4,ValueColumn
data1,name,data3,data4,Patient's "full" name
data2,patient_condition,data3,data4,<b>Stable</b> condition
data3,notes,data3,data4,See [section] for {details}"""

        path = create_temp_csv(csv_content)
        try:
            result = read_key_value_csv_path(
                path,
                key_col="KeyColumn",
                value_col="ValueColumn",
                key_prefix="patient",
                sanitize_values=True,
            )
            assert result == {
                "patient_name": "Patients full name",
                "patient_condition": "Stable condition",
                "patient_notes": "See section for details",
            }
        finally:
            os.unlink(path)

    def test_sanitize_with_duplicates_concat(self):
        """Test sanitization with duplicate keys and concat policy."""
        csv_content = """Col1,KeyColumn,Col3,Col4,ValueColumn
data1,symptom,data3,data4,Patient reports "pain"
data2,symptom,data3,data4,<i>Swelling</i> observed
data3,symptom,data3,data4,[Bruising] noted"""

        path = create_temp_csv(csv_content)
        try:
            result = read_key_value_csv_path(
                path,
                key_col="KeyColumn",
                value_col="ValueColumn",
                sanitize_values=True,
                on_duplicate="concat",
                concat_sep=", ",
            )
            # Each value should be sanitized before concatenation
            assert result == {
                "symptom": "Patient reports pain, Swelling observed, Bruising noted",
            }
        finally:
            os.unlink(path)

    def test_sanitize_real_world_medical_text(self):
        """Test sanitization on real-world medical text examples."""
        csv_content = """Col1,FieldName,Col3,Col4,Description
data1,precautions,data3,data4,"If the answer to question 3 is ""yes"", what type of precautions are in place?"
data2,assessment,data3,data4,<b>Assessment:</b> Patient's condition is [stable]
data3,medication,data3,data4,Dosage: {amount: 10mg} Frequency: twice daily"""

        path = create_temp_csv(csv_content)
        try:
            result = read_key_value_csv_path(
                path,
                key_col="FieldName",
                value_col="Description",
                sanitize_values=True,
            )
            assert result == {
                "precautions": "If the answer to question 3 is yes, what type of precautions are in place?",
                "assessment": "Assessment: Patients condition is stable",
                "medication": "Dosage: amount: 10mg Frequency: twice daily",
            }
        finally:
            os.unlink(path)

    def test_sanitize_preserves_parentheses(self):
        """Test that sanitization preserves parentheses but removes brackets."""
        csv_content = """Col1,KeyColumn,Col3,Col4,ValueColumn
data1,q1,data3,data4,Text (with parentheses) and [brackets]
data2,q2,data3,data4,(Important) note with {braces}"""

        path = create_temp_csv(csv_content)
        try:
            result = read_key_value_csv_path(
                path,
                key_col="KeyColumn",
                value_col="ValueColumn",
                sanitize_values=True,
            )
            assert result == {
                "q1": "Text (with parentheses) and brackets",
                "q2": "(Important) note with braces",
            }
        finally:
            os.unlink(path)

    def test_sanitize_empty_values(self):
        """Test sanitization on empty and whitespace-only values."""
        csv_content = """Col1,KeyColumn,Col3,Col4,ValueColumn
data1,q1,data3,data4,
data2,q2,data3,data4,"   "
data3,q3,data3,data4,Actual content"""

        path = create_temp_csv(csv_content)
        try:
            result = read_key_value_csv_path(
                path,
                key_col="KeyColumn",
                value_col="ValueColumn",
                sanitize_values=True,
            )
            assert result == {
                "q1": "",
                "q2": "",
                "q3": "Actual content",
            }
        finally:
            os.unlink(path)

    def test_sanitize_unicode_characters(self):
        """Test that Unicode characters are preserved during sanitization."""
        csv_content = """Col1,KeyColumn,Col3,Col4,ValueColumn
data1,q1,data3,data4,Café "coffee" shop
data2,q2,data3,data4,<b>中文</b> text
data3,q3,data3,data4,Emoji 😀 "test" [brackets]"""

        path = create_temp_csv(csv_content)
        try:
            result = read_key_value_csv_path(
                path,
                key_col="KeyColumn",
                value_col="ValueColumn",
                sanitize_values=True,
            )
            assert result == {
                "q1": "Café coffee shop",
                "q2": "中文 text",
                "q3": "Emoji 😀 test brackets",
            }
        finally:
            os.unlink(path)

    def test_sanitize_comprehensive(self):
        """Test comprehensive scenario with all sanitization features."""
        csv_content = """ID,FieldName,Type,Required,Description
1,patient_status,string,yes,"<b>Status:</b> If ""active"", proceed with [assessment]"
2,notes,text,no,Patient's condition is {improving}
3,patient_status,string,yes,"Additional note with (parentheses) and 'quotes'"""

        path = create_temp_csv(csv_content)
        try:
            result = read_key_value_csv_path(
                path,
                key_col="FieldName",
                value_col="Description",
                sanitize_values=True,
                on_duplicate="concat",
                concat_sep=" | ",
            )
            assert result == {
                "patient_status": "Status: If active, proceed with assessment | Additional note with (parentheses) and quotes",
                "notes": "Patients condition is improving",
            }
        finally:
            os.unlink(path)

