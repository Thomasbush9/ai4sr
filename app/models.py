from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime
import os

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    username = Column(String(50), unique=True, nullable=False)
    email = Column(String(120), unique=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    documents = relationship("Document", back_populates="user")

class Document(Base):
    __tablename__ = 'documents'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    filename = Column(String(255), nullable=False)
    file_path = Column(String(512), nullable=False)
    file_type = Column(String(10), nullable=False)
    num_chunks = Column(Integer, nullable=False)
    azure_search_index = Column(String(255), nullable=False)  # Name of the Azure Search index
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    user = relationship("User", back_populates="documents")
    chunks = relationship("DocumentChunk", back_populates="document")

class DocumentChunk(Base):
    __tablename__ = 'document_chunks'
    
    id = Column(Integer, primary_key=True)
    document_id = Column(Integer, ForeignKey('documents.id'), nullable=False)
    chunk_index = Column(Integer, nullable=False)  # Position of chunk in document
    content = Column(Text, nullable=False)
    azure_search_id = Column(String(255), nullable=False)  # ID in Azure Search
    
    document = relationship("Document", back_populates="chunks")

def init_db(database_url: str):
    """Initialize the database and create tables."""
    engine = create_engine(database_url)
    Base.metadata.create_all(engine)
    return engine 