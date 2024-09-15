import unittest
from datetime import datetime
from speakcare_emr_schema import EmrTableSchema, FieldTypes

class TestEmrTableSchema(unittest.TestCase):

    def setUp(self):
        self.valid_schema = {
            "name": "temperatureRecord",
            "fields": [
                {"name": "Units", "type": 'singleLineText'},
                {"name": "Temperature", "type": 'number'},
                {"name": "Route", "type": 'singleSelect', "options": {"choices": [{"name": "Tympanic"}, {"name": "Oral"}]}}
            ]
        }
        self.invalid_schema = {
            "name": "invalidRecord",
            "fields": [
                {"name": "Units", "type": 'singleLineText'},
                {"name": "Temperature", "type": 'number'},
                {"name": "Route", "type": 'singleSelect', "options": {"choices": [{"name": "Tympanic"}, {"name": "Oral"}]}}
            ]
        }

    def test_init_valid_schema(self):
        schema = EmrTableSchema("temperatureRecord", self.valid_schema)
        self.assertEqual(schema.table_name, "temperatureRecord")
        self.assertEqual(schema.table_schema, self.valid_schema)

    def test_init_invalid_schema(self):
        with self.assertRaises(ValueError) as context:
            EmrTableSchema("temperatureRecord", self.invalid_schema)
        self.assertTrue("Table name 'temperatureRecord' does not match the name in the schema 'invalidRecord'" in str(context.exception))

    def test_validate_record_valid(self):
        schema = EmrTableSchema("temperatureRecord", self.valid_schema)
        record = {
            "Units": "Fahrenheit",
            "Temperature": 103,
            "Route": "Tympanic"
        }
        is_valid, error_message = schema.validate_record(record)
        self.assertTrue(is_valid)
        self.assertIsNone(error_message)

    def test_validate_record_invalid_field(self):
        schema = EmrTableSchema("temperatureRecord", self.valid_schema)
        record = {
            "Units": "Fahrenheit",
            "Temperature": "high",
            "Route": "Tympanic"
        }
        is_valid, error_message = schema.validate_record(record)
        self.assertFalse(is_valid)
        self.assertIsNotNone(error_message)

    def test_validate_record_missing_unrequired_field(self):
        schema = EmrTableSchema("temperatureRecord", self.valid_schema)
        record = {
            "Temperature": 103,
            "Units": "Fahrenheit",
        }
        is_valid, error_message = schema.validate_record(record)
        self.assertTrue(is_valid)
        self.assertIsNone(error_message)

    def test_validate_record_missing_required_field(self):
        schema = EmrTableSchema("temperatureRecord", {
            "name": "temperatureRecord",
            "fields": [
                {"name": "Units", "type": 'singleLineText', "description": "required"},
                {"name": "Temperature", "type": 'number'},
                {"name": "Route", "type": 'singleSelect', "options": {"choices": [{"name": "Tympanic"}, {"name": "Oral"}]}}
            ]
        })
        record = {
            "Temperature": 103,
            "Route": "Tympanic"
        }
        is_valid, error_message = schema.validate_record(record)
        self.assertFalse(is_valid)
        self.assertEqual(error_message, "Validation error: Required field 'Units' is missing.")

    def test_validate_single_select_wrong_value(self):
        schema = EmrTableSchema("temperatureRecord", {
            "name": "temperatureRecord",
            "fields": [
                {"name": "Units", "type": 'singleSelect', "options": {"choices": [{"name": "Fahrenheit"}, {"name": "Celsius"}]}, "description": "required"},
                {"name": "Temperature", "type": 'number'},
                {"name": "Route", "type": 'singleSelect', "options": {"choices": [{"name": "Tympanic"}, {"name": "Oral"}]}}
            ]
        })
        record = {
            "Temperature": 103,
            "Units": "Kelvin",
            "Route": "Tympanic"
        }
        is_valid, error_message = schema.validate_record(record)
        self.assertFalse(is_valid)
        self.assertIsNotNone(error_message)   

    def test_validate_multi_select_correct_values(self):
        schema = EmrTableSchema("temperatureRecord", {
            "name": "temperatureRecord",
            "fields": [
                {"name": "Units", "type": 'singleSelect', "options": {"choices": [{"name": "Fahrenheit"}, {"name": "Celsius"}]}, "description": "required"},
                {"name": "Temperature", "type": 'number'},
                {"name": "Route", "type": 'multipleSelects', "options": {"choices": [{"name": "Tympanic"}, {"name": "Oral"}, {"name": "Rectal"}, {"name": "Axilla"}]}}
            ]
        })
        record = {
            "Temperature": 37,
            "Units": "Celsius",
            "Route": ["Tympanic", "Axilla"]
        }
        is_valid, error_message = schema.validate_record(record)
        self.assertTrue(is_valid)
        self.assertIsNone(error_message)        
    
    def test_validate_multi_select_incorrect_values(self):
        schema = EmrTableSchema("temperatureRecord", {
            "name": "temperatureRecord",
            "fields": [
                {"name": "Units", "type": 'singleSelect', "options": {"choices": [{"name": "Fahrenheit"}, {"name": "Celsius"}]}, "description": "required"},
                {"name": "Temperature", "type": 'number'},
                {"name": "Route", "type": 'multipleSelects', "options": {"choices": [{"name": "Tympanic"}, {"name": "Oral"}, {"name": "Rectal"}, {"name": "Axilla"}]}}
            ]
        })
        record = {
            "Temperature": 37,
            "Units": "Celsius",
            "Route": ["Tympanic", "Axilla", "Forehead", "Rectal"]
        }
        is_valid, error_message = schema.validate_record(record)
        self.assertFalse(is_valid)
        self.assertIsNotNone(error_message)        

    def test_validate_date_correct_value(self):
        schema = EmrTableSchema("testSchema", {
            "name": "testSchema",
            "fields": [
                {"name": "DateField", "type": "date"}
            ]
        })
        record = {"DateField": "2023-10-01"}
        is_valid, error_message = schema.validate_record(record)
        self.assertTrue(is_valid)
        self.assertIsNone(error_message)

    def test_validate_date_incorrect_value(self):
        schema = EmrTableSchema("testSchema", {
            "name": "testSchema",
            "fields": [
                {"name": "DateField", "type": "date"}
            ]
        })
        record = {"DateField": "01-10-2023"}
        is_valid, error_message = schema.validate_record(record)
        self.assertFalse(is_valid)
        self.assertIsNotNone(error_message)


    def test_validate_date_time_correct_value(self):
        schema = EmrTableSchema("testSchema", {
            "name": "testSchema",
            "fields": [
                {"name": "DateTimeField1", "type": "dateTime"},
                {"name": "DateTimeField2", "type": "dateTime"},
            ]
        })
        record = {
            "DateTimeField1": "2023-10-01T12:00:00Z",
            "DateTimeField2": "2023-10-01T12:00:00+00:00"
        }
        is_valid, error_message = schema.validate_record(record)
        self.assertTrue(is_valid)
        self.assertIsNone(error_message)

    def test_validate_date_time_incorrect_value(self):
        schema = EmrTableSchema("testSchema", {
            "name": "testSchema",
            "fields": [
                {"name": "DateTimeField", "type": "dateTime"}
            ]
        })
        dateTimeString = "2023-10-01 25:00:00"
        record = {"DateTimeField": dateTimeString}
        is_valid, error_message = schema.validate_record(record)
        self.assertFalse(is_valid)
        self.assertIsNotNone(error_message)


    def test_validate_percent_correct_value(self):
        schema = EmrTableSchema("testSchema", {
            "name": "testSchema",
            "fields": [
                {"name": "PercentField", "type": "percent"}
            ]
        })
        record = {"PercentField": 85}
        is_valid, error_message = schema.validate_record(record)
        self.assertTrue(is_valid)
        self.assertIsNone(error_message)

    def test_validate_percent_incorrect_value(self):
        schema = EmrTableSchema("testSchema", {
            "name": "testSchema",
            "fields": [
                {"name": "PercentField", "type": "percent"}
            ]
        })
        record = {"PercentField": 150}
        is_valid, error_message = schema.validate_record(record)
        self.assertFalse(is_valid)
        self.assertIsNotNone(error_message)

    def test_validate_checkbox_correct_value(self):
        schema = EmrTableSchema("testSchema", {
            "name": "testSchema",
            "fields": [
                {"name": "CheckboxField1", "type": "checkbox"},
                {"name": "CheckboxField2", "type": "checkbox"}
            ]
        })
        record = {
            "CheckboxField1": True,
            "CheckboxField2": False
        }
        is_valid, error_message = schema.validate_record(record)
        self.assertTrue(is_valid)
        self.assertIsNone(error_message)

    def test_validate_checkbox_incorrect_value(self):
        schema = EmrTableSchema("testSchema", {
            "name": "testSchema",
            "fields": [
                {"name": "CheckboxField", "type": "checkbox"}
            ]
        })
        record = {"CheckboxField": "yes"}
        is_valid, error_message = schema.validate_record(record)
        self.assertFalse(is_valid)
        self.assertIsNotNone(error_message)


    def test_validate_currency_correct_value(self):
        schema = EmrTableSchema("testSchema", {
            "name": "testSchema",
            "fields": [
                {"name": "CurrencyField", "type": "currency"}
            ]
        })
        record = {"CurrencyField": 100.50}
        is_valid, error_message = schema.validate_record(record)
        self.assertTrue(is_valid)
        self.assertIsNone(error_message)

    def test_validate_currency_incorrect_value(self):
        schema = EmrTableSchema("testSchema", {
            "name": "testSchema",
            "fields": [
                {"name": "CurrencyField", "type": "currency"}
            ]
        })
        record = {"CurrencyField": "one hundred"}
        is_valid, error_message = schema.validate_record(record)
        self.assertFalse(is_valid)
        self.assertIsNotNone(error_message)

if __name__ == '__main__':
    unittest.main()