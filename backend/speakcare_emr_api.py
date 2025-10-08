from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Tuple, Any


class EmrApi(ABC):
    """
    Interface for EMR API operations used by SpeakCareEmr.
    This interface defines the contract for Airtable API operations.
    """
    
    @abstractmethod
    def create_table(self, table: dict) -> Any:
        """Create a new table in Airtable."""
        pass
    
    @abstractmethod
    def retreive_all_tables_schema(self) -> List[dict]:
        """Retrieve schema for all tables in the base."""
        pass
    
    @abstractmethod
    def load_table(self, tableId: str) -> None:
        """Load a specific table into memory."""
        pass
    
    @abstractmethod
    def get_table_records(self, tableId: str) -> Optional[List[dict]]:
        """Get all records from a loaded table."""
        pass
    
    @abstractmethod
    def create_record(self, tableId: str, record: dict) -> Tuple[Optional[dict], Optional[str]]:
        """Create a new record in the specified table."""
        pass
    
    @abstractmethod
    def get_record(self, tableId: str, recordId: str) -> Optional[dict]:
        """Get a specific record by ID from the specified table."""
        pass
    
    @abstractmethod
    def update_record(self, tableId: str, recordId: str, record: dict) -> Any:
        """Update an existing record in the specified table."""
        pass
    
    @abstractmethod
    def delete_record(self, tableId: str, recordId: str) -> Any:
        """Delete a record from the specified table."""
        pass
