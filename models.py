# database models
from enum import Enum as PyEnum
from sqlalchemy import create_engine, Column, Integer, String, Text, JSON, Boolean, Enum, DateTime, ForeignKey, func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship, backref


# Define the base class for declarative models
Base = declarative_base()

class RecordState(PyEnum):
    PENDING = 'PENDING'       # created but not commited yet, pending for user
    ERRORS = 'ERRORS'         # created with errors or attempt to commit resutlted in errors
    COMMITTED = 'COMMITTED'   # commited to the EMR
    DISCARDED = 'DISCARDED'   # discared by user, not commited to the EMR


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
    patient_id = Column(String)  # External EMR patient ID
    nurse_name = Column(String)
    nurse_id = Column(String)  # External EMR nurse ID
    info = Column(JSON)  # Stores structured records in JSON format
    meta = Column(JSON)
    errors = Column(JSON)  # Stores any errors encountered during processing
    state = Column(Enum(RecordState), default=RecordState.PENDING)  # Use Enum type for state
    created_time = Column(DateTime, server_default=func.now())  # Auto-set on creation
    modified_time = Column(DateTime, onupdate=func.now())   # Auto-set on update

    # Foreign Key to link to the transcript from which this record was created
    transcript_id = Column(Integer, ForeignKey('Transcripts.id'))
    transcript = relationship('Transcripts', back_populates='medical_records')


# Create database engines
transcripts_engine = create_engine('sqlite:///db/transcripts.db')
medical_records_engine = create_engine('sqlite:///db/medical_records.db')

# Create tables
Base.metadata.create_all(transcripts_engine)
Base.metadata.create_all(medical_records_engine)

# Create session makers
TranscriptsDBSession = sessionmaker(bind=transcripts_engine)
MedicalRecordsDBSession = sessionmaker(bind=medical_records_engine)