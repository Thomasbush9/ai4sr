from typing import List, Dict, Any
import os
from pathlib import Path
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_openai import AzureOpenAIEmbeddings
from langchain_community.vectorstores import FAISS
import fitz  # PyMuPDF
import docx
import json
import logging

logger = logging.getLogger(__name__)

class DocumentProcessor:
    def __init__(self, embedding_config: Dict[str, str]):
        """Initialize with embedding configuration."""
        self.embedding_config = embedding_config
        self.embeddings = AzureOpenAIEmbeddings(
            model=embedding_config["deployment_name"],
            azure_endpoint=embedding_config["api_base"],
            api_key=embedding_config["api_key"],
            api_version=embedding_config["api_version"]
        )
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            length_function=len
        )
        logger.info(f"Initialized DocumentProcessor with embedding model: {embedding_config['deployment_name']}")
        logger.info(f"Using embedding endpoint: {embedding_config['api_base']}")

    def extract_text(self, file_path: str) -> str:
        """Extract text from various document formats."""
        file_extension = Path(file_path).suffix.lower()
        logger.info(f"Extracting text from {file_path} with extension {file_extension}")
        
        if file_extension == '.pdf':
            return self._extract_from_pdf(file_path)
        elif file_extension == '.docx':
            return self._extract_from_docx(file_path)
        elif file_extension == '.txt':
            return self._extract_from_txt(file_path)
        else:
            raise ValueError(f"Unsupported file format: {file_extension}")

    def _extract_from_pdf(self, file_path: str) -> str:
        """Extract text from PDF file."""
        doc = fitz.open(file_path)
        text = ""
        for page in doc:
            text += page.get_text()
        logger.info(f"Extracted {len(text)} characters from PDF")
        return text

    def _extract_from_docx(self, file_path: str) -> str:
        """Extract text from DOCX file."""
        doc = docx.Document(file_path)
        text = "\n".join([paragraph.text for paragraph in doc.paragraphs])
        logger.info(f"Extracted {len(text)} characters from DOCX")
        return text

    def _extract_from_txt(self, file_path: str) -> str:
        """Extract text from TXT file."""
        with open(file_path, 'r', encoding='utf-8') as f:
            text = f.read()
        logger.info(f"Extracted {len(text)} characters from TXT")
        return text

    def create_chunks(self, text: str) -> List[str]:
        """Split text into chunks."""
        chunks = self.text_splitter.split_text(text)
        logger.info(f"Created {len(chunks)} chunks from text")
        return chunks

    def generate_embeddings(self, chunks: List[str], index_dir: str) -> None:
        """Generate and store embeddings for chunks."""
        logger.info(f"Generating embeddings for {len(chunks)} chunks using {self.embedding_config['deployment_name']}")
        try:
            # Create FAISS index
            vectorstore = FAISS.from_texts(chunks, self.embeddings)
            
            # Save index with deserialization allowed
            vectorstore.save_local(
                index_dir  # Safe since we created these indices
            )
            logger.info(f"Saved embeddings to {index_dir}")
        except Exception as e:
            logger.error(f"Error generating embeddings: {str(e)}")
            raise

    def process_document(self, file_path: str, index_dir: str) -> Dict[str, Any]:
        """Process a document and store its embeddings."""
        logger.info(f"Processing document: {file_path}")
        
        try:
            # Extract text
            text = self.extract_text(file_path)
            
            # Create chunks
            chunks = self.create_chunks(text)
            
            # Generate and store embeddings
            self.generate_embeddings(chunks, index_dir)
            
            # Return metadata
            metadata = {
                "filename": Path(file_path).name,
                "num_chunks": len(chunks),
                "chunks": chunks
            }
            logger.info(f"Successfully processed document: {metadata['filename']}")
            return metadata
            
        except Exception as e:
            logger.error(f"Error processing document: {str(e)}")
            raise 