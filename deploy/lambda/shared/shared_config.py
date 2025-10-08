# shared_config.py
# Shared configuration data for all lambda functions

# Dummy nurses data - replace with database integration later
DUMMY_NURSES = [
    {
        "userId": "nurse001",
        "firstName": "Jane",
        "lastName": "Smith",
        "nickname": "Jane",
        "username": "jane.smith"
    },
    {
        "userId": "nurse002", 
        "firstName": "Mike",
        "lastName": "Johnson",
        "nickname": "Mike",
        "username": "mike.johnson"
    },
    {
        "userId": "nurse003",
        "firstName": "Sarah",
        "lastName": "Wilson",
        "nickname": "Sarah",
        "username": "sarah.wilson"
    },
    {
        "userId": "nurse004",
        "firstName": "David",
        "lastName": "Brown",
        "nickname": "Dave",
        "username": "david.brown"
    },
    {
        "userId": "nurse005",
        "firstName": "Taylor",
        "lastName": "Swift",
        "nickname": "Tay",
        "username": "taylor.swift"
    },
    {
        "userId": "nurse006",
        "firstName": "Lisa",
        "lastName": "Garcia",
        "nickname": "Lisa",
        "username": "lisa.garcia"
    }
]

# Allowed shift types
ALLOWED_SHIFTS = [
    "morning",
    "evening", 
    "night"
]

# Allowed corridor names
ALLOWED_CORRIDORS = [
    "Corridor 1",
    "Corridor 2",
    "Corridor 3",
    "Corridor 67B"
]

def get_nurses_for_facility(facility_id: str) -> list:
    """Get nurses for a specific facility - placeholder for database integration"""
    # For now, return all nurses regardless of facility
    # Later this will query the database based on facility_id
    return DUMMY_NURSES.copy()

def get_allowed_shifts() -> list:
    """Get allowed shift types - placeholder for database integration"""
    # Later this will query the database or config
    return ALLOWED_SHIFTS.copy()

def get_allowed_corridors() -> list:
    """Get allowed corridor names - placeholder for database integration"""
    # Later this will query the database or config  
    return ALLOWED_CORRIDORS.copy()

def find_nurse_by_name(full_name: str) -> dict:
    """Find a nurse by their full name (case-insensitive partial match)"""
    if not full_name:
        return None
    
    full_name_lower = full_name.lower().strip()
    
    # Try exact match first (firstName + lastName)
    for nurse in DUMMY_NURSES:
        nurse_full_name = f"{nurse['firstName']} {nurse['lastName']}".lower()
        if nurse_full_name == full_name_lower:
            return nurse
    
    # Try partial match (first name or last name)
    for nurse in DUMMY_NURSES:
        input_name_parts = full_name_lower.split()
        
        # Check if any part of input matches first name or last name
        for input_part in input_name_parts:
            if (input_part in nurse['firstName'].lower() or 
                input_part in nurse['lastName'].lower() or
                nurse['firstName'].lower() in input_part or
                nurse['lastName'].lower() in input_part):
                return nurse
    
    return None
