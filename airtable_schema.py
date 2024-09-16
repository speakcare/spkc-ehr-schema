from enum import Enum as PyEnum
from datetime import datetime
import logging
from speakcare_logging import create_logger

# Logger setup
schema_logger = create_logger('emr.schema')

class FieldTypes(PyEnum):
    NUMBER = 'number'
    SINGLE_LINE_TEXT = 'singleLineText'
    MULTI_LINE_TEXT = 'multilineText'
    SINGLE_SELECT = 'singleSelect'
    MULTI_SELECT = 'multipleSelects'
    DATE = 'date'
    DATE_TIME = 'dateTime'
    PERCENT = 'percent'
    CHECKBOX = 'checkbox'
    CURRENCY = 'currency'

_validation_functions_registry = {}

def register_validation_function(field_type):
    global _validation_functions_registry
    def decorator(func):
        _validation_functions_registry[field_type] = func
        return func
    return decorator

class AirtableSchema:
    def __init__(self, table_name, table_schema):
        if table_name != table_schema.get("name"):
            raise ValueError(f"Table name '{table_name}' does not match the name in the schema '{table_schema.get('name')}'")

        self.table_name = table_name
        self.table_schema = table_schema
        self.__field_registry = {}
        self.logger = schema_logger
        self.__initialize_field_registry()
        
    def __initialize_field_registry(self):
        for field in self.table_schema.get("fields", []):
            field_name = field.get("name")
            field_type = FieldTypes(field.get("type")) #if type is not in FieldTypes, it will raise an error
            field_options = field.get("options", {})
            field_description = field.get("description", "")
            is_required = "required" in field_description.lower()
            self.__field_registry[field_name] = {
                "type": field_type,
                "options": field_options,
                "required": is_required
            }    
    def get_schema(self):
        return self.table_schema
    
    def get_name(self):
        return self.table_name
    
    def validate_record(self, record, checkRequired: bool=True):
        """
        Takes a record and validates that it adheres to this schema
        For record update validation, set checkRequired to False as we allow partial updates
        """
        try:
            # Check for required fields only if checkRequired is True
            if checkRequired:
                for field_name, field_info in self.__field_registry.items():
                    if field_info.get("required") and field_name not in record:
                        error_message = f"Validation error: Required field '{field_name}' is missing."
                        self.logger.error(error_message)
                        return False, error_message
            
            # Validate each field in the record
            for field_name, field_value in record.items():
                if field_name in self.__field_registry:
                    field_info = self.__field_registry[field_name]
                    field_type = FieldTypes(field_info["type"])
                    field_options = field_info["options"]
                    is_valid, error_message = self.__validate_field(field_type, field_value, field_options)
                    if not is_valid:
                        error_message = f"Validation error for field '{field_name}': {error_message}"
                        self.logger.error(error_message)
                        return False, error_message
                else:
                    error_message = f"Field name '{field_name}' does not exist in the schema."
                    self.logger.error(error_message)
                    return False, error_message
            return True, None
        except Exception as e:
            error_message = f"Validation error: {e}"
            self.logger.error(error_message)
            return False, error_message
        
    def validate_partial_record(self, record):
        """
        Validates a partial record update
        """
        return self.validate_record(record, checkRequired=False)
    

    def __validate_field(self, field_type: FieldTypes, value, options=None):
        """
        Takes a field name and a value and validates that it adheres to the schema
        """
        global _validation_functions_registry 
        try:
            validation_function = _validation_functions_registry.get(field_type)
            if validation_function:
                return validation_function(self, value, options)
            else:
                error_message = f"No validation function found for field type '{field_type}'."
                self.logger.error(error_message)
                return False, error_message
        except Exception as e:
            error_message = f"Validation function error: {e}"
            self.logger.error(error_message)
            return False, error_message

    @register_validation_function(FieldTypes.NUMBER)
    def __validate_number(self, value, options=None):
        """
        Validates a number field
        """
        try:
            if isinstance(value, (int, float)):
                return True, ""

            # Check if the value is a string that can be converted to a number
            if isinstance(value, str):
                try:
                    # Attempt to convert the string to a float
                    float(value)
                    return True, ""
                except ValueError:
                    raise ValueError(f"Value '{value}' cannot be converted to a number.")

            # Raise an exception for all other types
            raise ValueError(f"Invalid type for number field: {type(value)}")
        except Exception as e:
            self.logger.error(f"Number validation error: {e}")
            return False, str(e)

    @register_validation_function(FieldTypes.SINGLE_LINE_TEXT)        
    def __validate_single_line_text(self, value, options=None):
        """
        Validates a single line text field
        """
        if isinstance(value, str) and '\n' not in value:
            return True, ""
        else:
            error_message = f"Single line text validation error: Value '{value}' is not a valid single line string."
            self.logger.error(error_message)
            return False, error_message
        

    @register_validation_function(FieldTypes.MULTI_LINE_TEXT)
    def __validate_multi_line_text(self, value, options=None):
        """
        Validates a multi line text field
        """
        if isinstance(value, str):
            return True, ""
        else:
            error_message = f"Multi line text validation error: Value '{value}' is not a valid multi line string."
            self.logger.error(error_message)
            return False, error_message
        
    @register_validation_function(FieldTypes.SINGLE_SELECT)
    def __validate_single_select(self, value, options=None):
        """
        Validates a single select field
        """
        if not isinstance(value, str) or options is None:
            error_message = f"Single select validation error: Value '{value}' is not a valid single select option."
            self.logger.error(error_message)
            return False, error_message
        for choice in options.get("choices", []):
            if choice.get("name") == value:
                return True, ""
        error_message = f"Single select validation error: Value '{value}' is not a valid choice."
        self.logger.error(error_message)
        return False, error_message

    @register_validation_function(FieldTypes.MULTI_SELECT)
    def __validate_multi_select(self, value, options=None):
        """
        Validates a multi select field
        """
        if not isinstance(value, list) or options is None:
            error_message = f"Multi select validation error: Value '{value}' is not a valid multi select option."
            self.logger.error(error_message)
            return False, error_message
        allowed_choices = {choice.get("name") for choice in options.get("choices", [])}
        for item in value:
            if not isinstance(item, str) or item not in allowed_choices:
                error_message = f"Multi select validation error: Value '{item}' is not a valid choice."
                self.logger.error(error_message)
                return False, error_message
        return True, ""

    @register_validation_function(FieldTypes.DATE)
    def __validate_date(self, value, options=None):
        """
        Validates that the string is in ISO date format (YYYY-MM-DD)
        """
        if not isinstance(value, str):
            error_message = f"Date validation error: Value '{value}' is not a valid date string."
            self.logger.error(error_message)
            return False, error_message
        try:
            datetime.fromisoformat(value)
            return True, ""
        except ValueError:
            error_message = f"Date validation error: Value '{value}' is not a valid ISO date."
            self.logger.error(error_message)
            return False, error_message
        
 
    @register_validation_function(FieldTypes.DATE_TIME)
    def __validate_date_time(self, value, options=None):
        """
        Validates a date_time field
        """
        if not isinstance(value, str):
            error_message = f"Date-time validation error: Value '{value}' is not a valid date-time string."
            self.logger.error(error_message)
            return False, error_message

        # Replace 'Z' with '+00:00' to use datetime.fromisoformat
        if value.endswith('Z'):
            value = value[:-1] + '+00:00'

        try:
            # Attempt to parse the string with datetime.fromisoformat()
            datetime.fromisoformat(value)
            return True, ""
        except ValueError:
            error_message = f"Date-time validation error: Value '{value}' is not a valid ISO date-time."
            self.logger.error(error_message)
            return False, error_message    
        

    @register_validation_function(FieldTypes.PERCENT)
    def __validate_percent(self, value, options=None):
        """
        Validates that the value is a percentage (0 to 100 inclusive).
        The value can be a string that represents a number.
        """
        if isinstance(value, str):
            try:
                value = float(value)
            except ValueError:
                error_message = f"Percent validation error: Value '{value}' cannot be converted to a percent."
                self.logger.error(error_message)
                return False, error_message
        if isinstance(value, (int, float)) and 0 <= value <= 100:
            return True, ""
        else:
            error_message = f"Percent validation error: Value '{value}' is not a valid percent (0-100)."
            self.logger.error(error_message)
            return False, error_message
    
    @register_validation_function(FieldTypes.CHECKBOX)
    def __validate_checkbox(self, value, options=None):
        """
        Validates that the value is a boolean.
        """
        if isinstance(value, bool):
            return True, ""
        else:
            error_message = f"Checkbox validation error: Value '{value}' is not a valid boolean for checkbox."
            self.logger.error(error_message)
            return False, error_message

    @register_validation_function(FieldTypes.CURRENCY)
    def __validate_currency(self, value, options=None):
        """
        Validates that the value is a number or a string convertible to a number.
        """
        if isinstance(value, (int, float)):
            return True, ""
        if isinstance(value, str):
            try:
                float(value)
                return True, ""
            except ValueError:
                error_message = f"Currency validation error: Value '{value}' cannot be converted to a currency."
                self.logger.error(error_message)
                return False, error_message
        else:
            error_message = f"Currency validation error: Invalid type for currency field: {type(value)}"
            self.logger.error(error_message)
            return False, error_message
