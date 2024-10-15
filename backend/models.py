# database models
from enum import Enum as PyEnum
from sqlalchemy import create_engine, Column, Integer, String, Text, JSON, Boolean, Enum, DateTime, ForeignKey, ARRAY, func
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker, scoped_session, relationship, backref
from sqlalchemy.ext.mutable import MutableDict, MutableList
from sqlalchemy.types import JSON
import os
import atexit
from os_utils import ensure_directory_exists
from speakcare_logging import create_logger

# Define the base class for declarative models


Base = declarative_base()
logger = create_logger(__name__)

class RecordState(PyEnum):
    PENDING = 'PENDING'       # created but not commited yet, pending for user
    ERRORS = 'ERRORS'         # created with errors or attempt to commit resutlted in errors
    COMMITTED = 'COMMITTED'   # commited to the EMR
    DISCARDED = 'DISCARDED'   # discared by user, not commited to the EMR

class TranscriptState(PyEnum):
    NEW       = 'NEW'               # new transcript, not processed yet   
    PROCESSED = 'PROCESSED'        # Processed transcript, converted to medical records and should be in the MediaclRecords table
    ERRORS    = 'ERRORS'         # processed transcript with errors

class RecordType(PyEnum):
    MEDICAL_RECORD = 'MEDICAL_RECORD'
    ASSESSMENT = 'ASSESSMENT'

# Define the RawTextSession model
class Transcripts(Base):
    __tablename__ = 'Transcripts'
    id = Column(Integer, primary_key=True)
    text = Column(Text)
    state = Column(Enum(TranscriptState), default=TranscriptState.NEW)
    errors = Column(MutableList.as_mutable(JSON), default=[])
    created_time = Column(DateTime, server_default=func.now())  # Auto-set on creation
    modified_time = Column(DateTime, onupdate=func.now())  # Auto-set on update

    # Reverse relationship: list of medical records created from this transcript
    medical_records = relationship('MedicalRecords', back_populates='transcript', cascade="all, delete-orphan")


# Define the MedicalRecords model
class MedicalRecords(Base):
    __tablename__ = 'MedicalRecords'
    id = Column(Integer, primary_key=True)
    emr_record_id = Column(String)  # Internal unique EMR record ID
    emr_url = Column(String)  # URL to the EMR record
    type = Column(Enum(RecordType), default=RecordType.MEDICAL_RECORD)  # Use Enum type for record type
    table_name = Column(String)  # Table name in the external EMR system
    patient_name = Column(String)
    patient_id = Column(String)  # External EMR application patient ID
    nurse_name = Column(String)
    nurse_id = Column(String)  # External EMR application nurse ID
    fields = Column(MutableDict.as_mutable(JSON), nullable=False)  # Stores structured records in JSON format
    # TODO: Add sections list for admissions. Should be able to be null
    sections = Column(MutableList.as_mutable(JSON), default=[])
    errors = Column(MutableList.as_mutable(JSON), default=[])
    state = Column(Enum(RecordState), default=RecordState.PENDING)  # Use Enum type for state
    created_time = Column(DateTime, server_default=func.now())  # Auto-set on creation
    modified_time = Column(DateTime, onupdate=func.now())   # Auto-set on update

    # Foreign Key to link to the transcript from which this record was created
    transcript_id = Column(Integer, ForeignKey('Transcripts.id'))
    transcript = relationship('Transcripts', back_populates='medical_records')


class SpeakCareDB:
    DB_FILE_NAME     = 'speakcare.db'

    def __init__(self, db_directory: str):
        # Create database engines
        self.db_path = ensure_directory_exists(db_directory)
        speakcare_sqlite_db = f'sqlite:///{db_directory}/{SpeakCareDB.DB_FILE_NAME}'#medical_records.db'
        logger.debug(f"Creating SpeakCare database at {speakcare_sqlite_db}")
        self.speakcare_db_engine = create_engine(speakcare_sqlite_db)
        # Create tables
        Base.metadata.create_all(self.speakcare_db_engine)
        self.SpeakCareDBSession = scoped_session(sessionmaker(bind=self.speakcare_db_engine))
        atexit.register(self.__cleanup)
    
    def __cleanup(self):
        # Clean up sessions and dispose of engines
        self.SpeakCareDBSession.remove()
        self.speakcare_db_engine.dispose()
        logger.debug("Cleaned up database sessions and disposed of engines.")

    def do_cleanup(self, delete_db_files = False):
        self.__cleanup()
        atexit.unregister(self.__cleanup)
        if delete_db_files:
            logger.debug(f"Deleting database files from {self.db_path}")
            os.remove(f"{self.db_path}/{SpeakCareDB.DB_FILE_NAME}")
            logger.debug(f"Deleting database directory {self.db_path}")
            os.rmdir(self.db_path)
        else:
            logger.debug(f"Database files are not deleted from {self.db_path}")


__singletonDbInstance = None
def init_speakcare_db(db_directory = None):
    """
    Provides access to the singleton instance of SpeakCareDB.
    Initializes the instance if it hasn't been created yet.
    :param config: Optional configuration dictionary for initializing the instance.
    :return: Singleton instance of SpeakCareDB.
    """
    global __singletonDbInstance
    if __singletonDbInstance is None:
        if db_directory is None:
            db_directory = 'db'
        logger.debug(f"Initializing SpeakCareDB with db_directory: {db_directory}")
        __singletonDbInstance = SpeakCareDB(db_directory)
    return __singletonDbInstance

def get_speakcare_db_instance():
    return init_speakcare_db()