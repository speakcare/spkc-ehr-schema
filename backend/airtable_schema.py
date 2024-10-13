from enum import Enum as PyEnum
from datetime import datetime
import logging
import copy
import json
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

_field_validation_functions_registry = {}

def register_validation_function(field_type):
    global _field_validation_functions_registry
    def decorator(func):
        _field_validation_functions_registry[field_type] = func
        return func
    return decorator

_field_schema_registry = {}
def register_field_type_schema(field_type):
    global _field_schema_registry
    def decorator(func):
        _field_schema_registry[field_type] = func
        return func
    return decorator

class AirtableSchema:

    __table_schema_properties = ["name", "fields"]

    def __init__(self, table_name, table_schema):
        if table_name != table_schema.get("name"):
            raise ValueError(f"Table name '{table_name}' does not match the name in the schema '{table_schema.get('name')}'")

        self.logger = schema_logger
        self.table_name = table_name
        self.__create_table_schema(table_schema)
        self.logger.debug(f"Created schema for table '{self.table_name}'.") 
        
               
    def __create_table_schema(self, table_schema):
        """
        Create a canonical schema from an Airtable schema
        """
        # rebuild the schema with only the properties we care about
        self.table_schema = {key: value for key, value in table_schema.items() if key in self.__table_schema_properties}
        # initialize the field registry
        self.__create_field_registry() 
        

    def __create_field_registry(self):
        self.__field_registry = {}
        fields = self.table_schema.get("fields", [])
        for i, field in enumerate(fields):
            field_name = field.get("name")
            field_type = FieldTypes(field.get("type"))  # if type is not in FieldTypes, it will raise an error
            #field_schema = field.get("schema", {})
            field_schema = self.__create_field_schema(field_type, field)
            if not field_schema:
                error_message = f"Error creating schema for table '{self.table_name}' for field name '{field_name}' field {field}."
                self.logger.error(error_message)
                raise ValueError(error_message)
            
            # Replace the field schema with the canonical schema
            fields[i] = field_schema
            
            field_options = field.get("options", {})
            field_description = field.get("description", "")
            is_required = "required" in field_description.lower()
            self.__field_registry[field_name] = {
                "type": field_type,
                "options": field_options,
                "required": is_required
            }
        
        # Update the table schema with the modified fields
        self.table_schema["fields"] = fields

    def get_schema(self):
        return self.table_schema
    
    def get_name(self):
        return self.table_name
        
    def validate_record(self, record,  errors, checkRequired: bool=True):
        """
        Takes a record and validates that it adheres to this schema
        For record update validation, set checkRequired to False as we allow partial updates
        """
        
        validated_fields = {}
        all_valid = True
        try:
            # Check for required fields only if checkRequired is True
            if checkRequired:
                for field_name, field_info in self.__field_registry.items():
                    if field_info.get("required") and field_name not in record:
                        error_message = f"Validation error: Required field '{field_name}' is missing."
                        self.logger.error(error_message)
                        errors.append(error_message)
                        all_valid = False
            
            # Validate each field in the record
            for field_name, field_value in record.items():
                if field_name in self.__field_registry:
                    field_info = self.__field_registry[field_name]
                    field_type = FieldTypes(field_info["type"])
                    field_options = field_info["options"]
                    validated_value, error_message = self.__validate_field(field_type, field_value, field_options)
                    if validated_value is not None:
                        validated_fields[field_name] = validated_value
                        if error_message:
                            error_message = f"Validation warning for field '{field_name}': {error_message}"
                            self.logger.warning(error_message)
                            errors.append(error_message)
                    else:
                        error_message = f"Validation error for field '{field_name}': {error_message}"
                        self.logger.error(error_message)
                        errors.append(error_message)
                        if field_info.get("required"): # validation failed for a required field
                            all_valid = False
                        
                else:
                    error_message = f"Field name '{field_name}' does not exist in the schema."
                    self.logger.error(error_message)
                    errors.append(error_message)
                    # Here we don't set is_valid to False as we can silently ignore fields that are not in the schema
            
            return all_valid, validated_fields
        except Exception as e:
            error_message = f"Validation error: {e}"
            self.logger.error(error_message)
            errors.append(error_message)
            return False, validated_fields

    def validate_partial_record(self, record, errors):
        """
        Validates a partial record update
        """
        return self.validate_record(record, errors=errors, checkRequired=False)
    

    def __validate_field(self, field_type: FieldTypes, value, options=None):
        """
        Takes a field name and a value and validates that it adheres to the schema
        """
        global _field_validation_functions_registry 
        try:
            validation_function = _field_validation_functions_registry.get(field_type)
            if validation_function:
                return validation_function(self, value, options)
            else:
                error_message = f"No validation function found for field type '{field_type}'."
                self.logger.error(error_message)
                return None, error_message
        except Exception as e:
            error_message = f"Validation function error: {e}"
            self.logger.error(error_message)
            return None, error_message

    def __create_field_schema(self, field_type: FieldTypes, airtable_schema: dict):
        global _field_schema_registry
        field_schema_function = _field_schema_registry.get(field_type)
        if field_schema_function:
            try:
                return field_schema_function(self, airtable_schema)
            except Exception as e:
                error_message = f"Field schema function error: {e}"
                self.logger.error(error_message)
                return None
        else:
            error_message = f"No schema function found for field type '{field_type}'."
            self.logger.error(error_message)
            return None


    """ 
    Field type schema functions 
    For each type provide a function that validates the field and a function that converts 
    from Airtable schema to the SpeakCare canonical schema
    """


    ### Number field schema
    @register_validation_function(FieldTypes.NUMBER)
    def __validate_number(self, value, options=None):
        """
        Validates a number field
        """
        try:
            if isinstance(value, (int, float)):
                return value, ""

            # Check if the value is a string that can be converted to a number
            if isinstance(value, str):
                try:
                    # Attempt to convert the string to a float
                    float_val = float(value)
                    return float_val, ""
                except ValueError:
                    raise ValueError(f"Value '{value}' cannot be converted to a number.")

            # Raise an exception for all other types
            raise ValueError(f"Invalid type for number field: {type(value)}")
        except Exception as e:
            self.logger.error(f"Number validation error: {e}")
            return None, str(e)
        
    @register_field_type_schema(FieldTypes.NUMBER)
    def __number_schema(self, airtable_schema: dict):
        #    "type": "number",
        #     "options": {
        #         "format": "precision: 1"
        #     },
        #     "name": "name",
        #     "description": "required"

        return {
            "type": FieldTypes.NUMBER.value,
            "name": f"{airtable_schema.get('name')}",
            "options": {
                "format": f"precision: {airtable_schema.get('options').get('precision')}",
                #"format": f"precision: {airtable_schema.get('options', {}).get('precision', 0)}",
            },
            # user dictionary comprehension to add description only if it exists
            **({"description": airtable_schema.get('description')} if airtable_schema.get('description') is not None else {})
        }


    ### Single line text field schema
    @register_validation_function(FieldTypes.SINGLE_LINE_TEXT)        
    def __validate_single_line_text(self, value, options=None):
        """
        Validates a single line text field
        """
        if isinstance(value, str) and '\n' not in value:
            return value, ""
        else:
            error_message = f"Single line text validation error: Value '{value}' is not a valid single line string."
            self.logger.error(error_message)
            return None, error_message
        
    @register_field_type_schema(FieldTypes.SINGLE_LINE_TEXT)
    def __single_line_text_schema(self, airtable_schema: dict):
        return {
            "type": FieldTypes.SINGLE_LINE_TEXT.value,
            "name": f"{airtable_schema.get('name')}",
            **({"description": airtable_schema.get('description')} if airtable_schema.get('description') is not None else {})
        }
        # {
        #     "type": "singleLineText",
        #     "name": "TreatmentPlan"
        # },


    ### Multi line text field schema
    @register_validation_function(FieldTypes.MULTI_LINE_TEXT)
    def __validate_multi_line_text(self, value, options=None):
        """
        Validates a multi line text field
        """
        if isinstance(value, str):
            return value, ""
        else:
            error_message = f"Multi line text validation error: Value '{value}' is not a valid multi line string."
            self.logger.error(error_message)
            return None, error_message
        

    @register_field_type_schema(FieldTypes.MULTI_LINE_TEXT)
    def __multi_line_text_schema(self, airtable_schema: dict):
        # {
        #     "type": "multilineText",
        #     "name": "Notes"
        # },
        return {
            "type": FieldTypes.MULTI_LINE_TEXT.value,
            "name": f"{airtable_schema.get('name')}",
            **({"description": airtable_schema.get('description')} if airtable_schema.get('description') is not None else {})
        }


    ### Single select field schema
    @register_validation_function(FieldTypes.SINGLE_SELECT)
    def __validate_single_select(self, value, options=None):
        """
        Validates a single select field
        """
        if not isinstance(value, str) or options is None:
            error_message = f"Single select validation error: Value '{value}' is not a valid single select option."
            self.logger.error(error_message)
            return None, error_message
        for choice in options.get("choices", []):
            if choice.get("name") == value:
                return value, ""
        error_message = f"Single select validation error: Value '{value}' is not a valid choice."
        self.logger.error(error_message)
        return None, error_message
    
    @register_field_type_schema(FieldTypes.SINGLE_SELECT)
    def __single_select_schema(self, airtable_schema: dict):
        # {
        #     "type": "singleSelect",
        #     "options": {
        #         "choices": [
        #             {
        #                 "name": "Wheelchair only",
        #             },
        #             {
        #                 "name": "Wheelchair/propels self",
        #             },
        #         ]
        #     },
        #     "name": "Ambulation device"
        # },
        return {
            "type": FieldTypes.SINGLE_SELECT.value,
            "name": f"{airtable_schema.get('name')}",
            "options": {
                "choices": [
                    {"name": choice["name"]}
                    for choice in airtable_schema.get("options", {}).get("choices", [])
                ]
            },
            **({"description": airtable_schema.get('description')} if airtable_schema.get('description') is not None else {})
        }

    ### Multi select field schema
    @register_validation_function(FieldTypes.MULTI_SELECT)
    def __validate_multi_select(self, value, options=None):
        """
        Validates a multi select field
        """
        error_prefix = "Multi select validation errors:"
        error_message = None
        if not isinstance(value, list) or options is None:
            error_message = error_prefix + f" Argumment '{value}' is not a valid multi select list option."
            self.logger.error(error_message)
            return None, error_message
        allowed_choices = {choice.get("name") for choice in options.get("choices", [])}
        validated_values_list = []
        for item in value:
            if isinstance(item, str) and item in allowed_choices:
                validated_values_list.append(item)
            else: #if not isinstance(item, str) or item not in allowed_choices:
                err = f" Value '{item}' is not a valid choice."
                self.logger.warning(error_prefix + err)
                error_message = (error_message + err) if error_message else (error_prefix + err)
        if len(validated_values_list) == 0:
            err = " No valid choices found."
            error_message = (error_message + err) if error_message else (error_prefix + err)
            self.logger.error(error_message)
            return None, error_message
        return validated_values_list, error_message
    
    
    @register_field_type_schema(FieldTypes.MULTI_SELECT)
    def __multi_select_schema(self, airtable_schema: dict):
        # {
        #     "type": "multipleSelects",
        #     "options": {
        #         "choices": [
        #             {
        #                 "name": "Wheelchair only",
        #             },
        #             {
        #                 "name": "Wheelchair/propels self",
        #             },
        #         ]
        #     },
        #     "name": "Ambulation device"
        # },
        return {
            "type": FieldTypes.MULTI_SELECT.value,
            "name": f"{airtable_schema.get('name')}",
            "options": {
                "choices": [
                    {"name": choice["name"]}
                    for choice in airtable_schema.get("options", {}).get("choices", [])
                ]
            },
            **({"description": airtable_schema.get('description')} if airtable_schema.get('description') is not None else {})
        }


    ### Date field schema
    @register_validation_function(FieldTypes.DATE)
    def __validate_date(self, value, options=None):
        """
        Validates that the string is in ISO date format (YYYY-MM-DD)
        """
        if not isinstance(value, str):
            error_message = f"Date validation error: Value '{value}' is not a string."
            self.logger.error(error_message)
            return None, error_message
        try:
            datetime.fromisoformat(value)
            return value, ""
        except ValueError:
            error_message = f"Date validation error: Value '{value}' is not a valid ISO date."
            self.logger.error(error_message)
            return None, error_message

    @register_field_type_schema(FieldTypes.DATE)
    def __date_schema(self, airtable_schema: dict):
        # {
        #     "type": "date",
        #     "options": {
        #         "standard": "ISO-8601",
        #         "format":   "YYYY-MM-DDT"
        #     },
        #     "name": "Admission Date",
        #     "description": "required"
        # },
        return {
            "type": FieldTypes.DATE.value,
            "name": f"{airtable_schema.get('name')}",
            "options": {
                "standard": "ISO-8601",
                "format": "YYYY-MM-DD"
            },
            **({"description": airtable_schema.get('description')} if airtable_schema.get('description') is not None else {})
        }

    ### Date-time field schema
    @register_validation_function(FieldTypes.DATE_TIME)
    def __validate_date_time(self, value, options=None):
        """
        Validates a date_time field
        """
        if not isinstance(value, str):
            error_message = f"Date-time validation error: Value '{value}' is not a string."
            self.logger.error(error_message)
            return None, error_message

        # Replace 'Z' with '+00:00' to use datetime.fromisoformat
        if value.endswith('Z'):
            value = value[:-1] + '+00:00'

        try:
            # Attempt to parse the string with datetime.fromisoformat()
            datetime.fromisoformat(value)
            return value, ""
        except ValueError:
            error_message = f"Date-time validation error: Value '{value}' is not a valid ISO date-time."
            self.logger.error(error_message)
            return None, error_message    
        
    @register_field_type_schema(FieldTypes.DATE_TIME)
    def __date_time_schema(self, airtable_schema: dict):
        return {
            "type": FieldTypes.DATE_TIME.value,
            "name": f"{airtable_schema.get('name')}",
            "options": {
                "standard": "ISO-8601",
                "format": "YYYY-MM-DDTHH:MM:SSZ",
                "timezone": "UTC"
            },
            **({"description": airtable_schema.get('description')} if airtable_schema.get('description') is not None else {})
        }
        # {
        #     "type": "dateTime",
        #     "options": {
        #         "standard": "ISO-8601",
        #         "format":   "YYYY-MM-DDTHH:MM:SSZ",
        #         "timezone": "UTC"
        #     },
        #     "name": "Admission Date",
        #     "description": "required"
        # },
        
    ### Percent field schema
    @register_validation_function(FieldTypes.PERCENT)
    def __validate_percent(self, value, options=None):
        """
        Validates that the value is a percentage (0 to 100 inclusive).
        The value can be a string that represents a number.
        """

        if isinstance(value, str):
            try:
                # convert the string to a float
                value = float(value)
            except ValueError:
                error_message = f"Percent validation error: Value '{value}' cannot be converted to a percent."
                self.logger.error(error_message)
                return False, error_message
        if isinstance(value, (int, float)) and 0 <= value <= 100:
            decimal = value / 100
            return decimal, ""
        else:
            error_message = f"Percent validation error: Value '{value}' is not a valid percent (0-100)."
            self.logger.error(error_message)
            return None, error_message
        
    @register_field_type_schema(FieldTypes.PERCENT)
    def __percent_schema(self, airtable_schema: dict):
        return {
            "type": FieldTypes.PERCENT.value,
            "name": f"{airtable_schema.get('name')}",
            "options": {
                "format": f"precision: {airtable_schema.get('options', {}).get('precision', 0)}",
                "min": 0,
                "max": 100
            },
            **({"description": airtable_schema.get('description')} if airtable_schema.get('description') is not None else {})
        }    
        #    "type": "percent",
        #     "options": {
        #         "format": "precision: 1"
        #         "min": 0,
        #         "max": 100
        #     },
        #     "name": "name",
        #     "description": "required"

    ### Checkbox field schema
    @register_validation_function(FieldTypes.CHECKBOX)
    def __validate_checkbox(self, value, options=None):
        """
        Validates that the value is a boolean.
        """
        if isinstance(value, bool):
            return value, ""
        else:
            error_message = f"Checkbox validation error: Value '{value}' is not a valid boolean for checkbox."
            self.logger.error(error_message)
            return None, error_message
        
    @register_field_type_schema(FieldTypes.CHECKBOX)
    def __checkbox_schema(self, airtable_schema: dict):
        return {
            "type": FieldTypes.CHECKBOX.value,
            "name": f"{airtable_schema.get('name')}",
            "options": {
                "format": "boolean"
            },
            **({"description": airtable_schema.get('description')} if airtable_schema.get('description') is not None else {})
        }
        # {
        #     "type": "checkbox",
        #     "options": {
        #         "format": "boolean"
        #     },
        #     "name": "FollowUpRequired"
        # },


    @register_validation_function(FieldTypes.CURRENCY)
    def __validate_currency(self, value, options=None):
        """
        Validates that the value is a number or a string convertible to a number.
        """
        if isinstance(value, (int, float)):
            return True, ""
        elif isinstance(value, str):
            try:
                float(value)
                return value, ""
            except ValueError:
                error_message = f"Currency validation error: Value '{value}' cannot be converted to a float."
                self.logger.error(error_message)
                return None, error_message
        else:
            error_message = f"Currency validation error: Invalid type for currency field: {type(value)}"
            self.logger.error(error_message)
            return None, error_message
        

    ### Currency field schema
    @register_field_type_schema(FieldTypes.CURRENCY)
    def __currency_schema(self, airtable_schema: dict):
        return {
            "type": FieldTypes.CURRENCY.value,
            "name": f"{airtable_schema.get('name')}",
            "options": {
                "format": f"precision: {airtable_schema.get('options', {}).get('precision', 0)}"
            },
            **({"description": airtable_schema.get('description')} if airtable_schema.get('description') is not None else {})
        }   
        #    "type": "percent",
        #     "options": {
        #         "format": "precision: 1",
        #     },
        #     "name": "name",
        #     "description": "required"