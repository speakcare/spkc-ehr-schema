

class TableSchemas:
    """Table schema definitions for testing purposes"""

    TEST_NURSES_FIELDS = [
        {
            "name": "Name",
            "type": "singleLineText",
            "description": "Nurse's full name"
        },
        {
            "name": "Specialization", 
            "type": "multipleSelects",
            "options": {
                "choices": [
                    {"name": "Cardiology"},
                    {"name": "Geriatrics"},
                    {"name": "Oncology"},
                    {"name": "Pediatrics"},
                    {"name": "Orthopedics"},
                    {"name": "Dermatology"},
                    {"name": "Neurology"}
                ]
            },
            "description": "Nurse's specializations"
        },
        {
            "name": "Schedule",
            "type": "singleLineText", 
            "description": "Work schedule and shifts"
        }
    ]
