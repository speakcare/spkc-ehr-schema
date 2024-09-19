# database models
from enum import Enum as PyEnum
from sqlalchemy import create_engine, Column, Integer, String, Text, JSON, Boolean, Enum, DateTime, ForeignKey, func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, scoped_session, relationship, backref
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.types import JSON
import os

# Define the base class for declarative models

# Ensure the ./db directory exists
db_directory = './db'
if not os.path.exists(db_directory):
    os.makedirs(db_directory)

Base = declarative_base()

class RecordState(PyEnum):
    PENDING = 'PENDING'       # created but not commited yet, pending for user
    ERRORS = 'ERRORS'         # created with errors or attempt to commit resutlted in errors
    COMMITTED = 'COMMITTED'   # commited to the EMR
    DISCARDED = 'DISCARDED'   # discared by user, not commited to the EMR

class TranscriptState(PyEnum):
    NEW = 'NEW'               # new transcript, not processed yet   
    DONE = 'DONE'             # Done transcript, ready to be converted to medical record
    ERRORS = 'ERRORS'         # processed transcript with errors

class RecordType(PyEnum):
    MEDICAL_RECORD = 'MEDICAL_RECORD'
    ASSESSMENT = 'ASSESSMENT'

# Define the RawTextSession model
class Transcripts(Base):
    __tablename__ = 'Transcripts'
    id = Column(Integer, primary_key=True)
    text = Column(Text)
    state = Column(Enum(TranscriptState), default=TranscriptState.NEW)
    errors = Column(JSON, default=[])  # Stores any errors encountered during processing
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
    fields = Column(MutableDict.as_mutable(JSON))  # Stores structured records in JSON format
    meta = Column(JSON)
    errors = Column(JSON, default=[])  # Stores any errors encountered during processing
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
TranscriptsDBSession = scoped_session(sessionmaker(bind=transcripts_engine))
MedicalRecordsDBSession =  scoped_session(sessionmaker(bind=medical_records_engine))