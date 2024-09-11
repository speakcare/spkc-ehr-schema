# database models
from sqlalchemy import create_engine, Column, Integer, String, Text, JSON, Boolean, Enum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Define the base class for declarative models
Base = declarative_base()

# Define the RawTextSession model
class Transcripts(Base):
    __tablename__ = 'Transcripts'
    id = Column(Integer, primary_key=True)
    text = Column(Text)
    meta = Column(JSON)  # Stores additional session information
    processed = Column(Boolean, default=False)

# Define the MedicalRecords model
class MedicalRecords(Base):
    __tablename__ = 'MedicalRecords'
    id = Column(Integer, primary_key=True)
    data = Column(JSON)  # Stores structured records in JSON format
    meta = Column(JSON)
    state = Column(String)  # e.g., 'new', 'approved', 'archived', 'discarded'

# Create database engines
transcripts_engine = create_engine('sqlite:///db/transcripts.db')
medical_records_engine = create_engine('sqlite:///db/medical_records.db')

# Create tables
Base.metadata.create_all(transcripts_engine)
Base.metadata.create_all(medical_records_engine)

# Create session makers
TranscriptsDBSession = sessionmaker(bind=transcripts_engine)
MedicalRecordsDBSession = sessionmaker(bind=medical_records_engine)