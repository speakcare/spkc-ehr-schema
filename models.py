# database models
from enum import Enum as PyEnum
from sqlalchemy import create_engine, Column, Integer, String, Text, JSON, Boolean, Enum, DateTime, func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Define the base class for declarative models
Base = declarative_base()

class RecordState(PyEnum):
    NEW = 'new'
    COMMITED = 'commited'
    DISCARDED = 'discarded'


class RecordType(PyEnum):
    MEDICAL_RECORD = 'medical_record'
    ASSESSMENT = 'assessment'
    ASSESSMENT_SECTION = 'assessment_section'

# Define the RawTextSession model
class Transcripts(Base):
    __tablename__ = 'Transcripts'
    id = Column(Integer, primary_key=True)
    text = Column(Text)
    meta = Column(JSON)  # Stores additional session information
    processed = Column(Boolean, default=False)
    errors = Column(JSON)  # Stores any errors encountered during processing
    created_time = Column(DateTime, server_default=func.now())  # Auto-set on creation
    modified_time = Column(DateTime, onupdate=func.now())  # Auto-set on update

# Define the MedicalRecords model
class MedicalRecords(Base):
    __tablename__ = 'MedicalRecords'
    id = Column(Integer, primary_key=True)
    emr_record_id = Column(String)  # External EMR record ID
    emr_url = Column(String)  # URL to the EMR record
    parent_id = Column(Integer) # For record sections only - ID of the parent record in the Sqlite database
    type = Column(Enum(RecordType), default=RecordType.MEDICAL_RECORD)  # Use Enum type for record type
    table_name = Column(String)  # Table name in the external EMR system
    patient_name = Column(String)
    nurse_name = Column(String)
    data = Column(JSON)  # Stores structured records in JSON format
    meta = Column(JSON)
    errors = Column(JSON)  # Stores any errors encountered during processing
    state = Column(Enum(RecordState), default=RecordState.NEW)  # Use Enum type for state
    created_time = Column(DateTime, server_default=func.now())  # Auto-set on creation
    modified_time = Column(DateTime, onupdate=func.now())   # Auto-set on update

# Create database engines
transcripts_engine = create_engine('sqlite:///db/transcripts.db')
medical_records_engine = create_engine('sqlite:///db/medical_records.db')

# Create tables
Base.metadata.create_all(transcripts_engine)
Base.metadata.create_all(medical_records_engine)

# Create session makers
TranscriptsDBSession = sessionmaker(bind=transcripts_engine)
MedicalRecordsDBSession = sessionmaker(bind=medical_records_engine)