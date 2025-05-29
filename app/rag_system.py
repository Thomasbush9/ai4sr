import dspy
from dspy.teleprompt import BootstrapFewShot
from typing import List, Dict, Any
import os
from dotenv import load_dotenv
from datetime import datetime
import json
from pathlib import Path
from document_processor import DocumentProcessor
from rag_module import RAGModule
from langchain_openai import AzureOpenAIEmbeddings
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
from models import init_db, User, Document
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

class RAGSystem:
    def __init__(self):
        # Initialize Azure OpenAI configuration for chat
        self.chat_config = {
            "api_key": os.getenv("AZURE_OPENAI_KEY"),
            "api_base": os.getenv("AZURE_OPENAI_ENDPOINT"),
            "api_version": os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview"),
            "deployment_name": os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")
        }
        
        # Initialize Azure OpenAI configuration for embeddings
        self.embedding_config = {
            "api_key": os.getenv("AZURE_OPENAI_EMBEDDING_KEY"),
            "api_base": os.getenv("AZURE_OPENAI_EMBEDDING_ENDPOINT"),
            "api_version": os.getenv("AZURE_OPENAI_EMBEDDING_API_VERSION", "2024-02-15-preview"),
            "deployment_name": os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME")
        }
        
        # Initialize Azure Search configuration
        self.azure_search_config = {
            "endpoint": os.getenv("AZURE_SEARCH_ENDPOINT"),
            "key": os.getenv("AZURE_SEARCH_KEY")
        }
        
        # Initialize database
        database_url = os.getenv("DATABASE_URL", "sqlite:///./rag.db")
        self.engine = init_db(database_url)
        Session = sessionmaker(bind=self.engine)
        self.db_session = Session()
        
        # Validate configurations
        self._validate_configs()
        
        # Initialize DSPy with Azure OpenAI
        try:
            dspy.configure(
                lm=dspy.LM(
                    model=f"azure/{self.chat_config['deployment_name']}",
                    api_key=self.chat_config["api_key"],
                    api_base=self.chat_config["api_base"],
                    api_version=self.chat_config["api_version"]
                )
            )
            logger.info("Successfully configured DSPy with Azure OpenAI")
        except Exception as e:
            logger.error(f"Failed to configure DSPy: {str(e)}")
            raise
        
        # Initialize components
        self.document_processor = DocumentProcessor(
            self.embedding_config,
            self.azure_search_config,
            self.db_session
        )
        self.rag_module = RAGModule()
        self.embeddings = AzureOpenAIEmbeddings(
            model=self.embedding_config["deployment_name"],
            azure_endpoint=self.embedding_config["api_base"],
            api_key=self.embedding_config["api_key"],
            api_version=self.embedding_config["api_version"]
        )
        
        logger.info("Initialized RAG system components")

    def _validate_configs(self):
        """Validate the Azure OpenAI and Azure Search configurations."""
        # Validate chat configuration
        chat_required_vars = ["api_key", "api_base", "deployment_name"]
        chat_missing_vars = [var for var in chat_required_vars if not self.chat_config[var]]
        
        if chat_missing_vars:
            error_msg = f"Missing required chat environment variables: {', '.join(chat_missing_vars)}"
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        # Validate embedding configuration
        embedding_required_vars = ["api_key", "api_base", "deployment_name"]
        embedding_missing_vars = [var for var in embedding_required_vars if not self.embedding_config[var]]
        
        if embedding_missing_vars:
            error_msg = f"Missing required embedding environment variables: {', '.join(embedding_missing_vars)}"
            logger.error(error_msg)
            raise ValueError(error_msg)
            
        # Validate Azure Search configuration
        search_required_vars = ["endpoint", "key"]
        search_missing_vars = [var for var in search_required_vars if not self.azure_search_config[var]]
        
        if search_missing_vars:
            error_msg = f"Missing required Azure Search environment variables: {', '.join(search_missing_vars)}"
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        # Log configurations (excluding sensitive data)
        logger.info("Chat Configuration:")
        logger.info(f"  Endpoint: {self.chat_config['api_base']}")
        logger.info(f"  Deployment: {self.chat_config['deployment_name']}")
        logger.info(f"  API Version: {self.chat_config['api_version']}")
        
        logger.info("Embedding Configuration:")
        logger.info(f"  Endpoint: {self.embedding_config['api_base']}")
        logger.info(f"  Deployment: {self.embedding_config['deployment_name']}")
        logger.info(f"  API Version: {self.embedding_config['api_version']}")
        
        logger.info("Azure Search Configuration:")
        logger.info(f"  Endpoint: {self.azure_search_config['endpoint']}")

    def create_user(self, username: str, email: str) -> User:
        """Create a new user or return existing user if email exists."""
        try:
            # Check if user with this email already exists
            existing_user = self.db_session.query(User).filter(User.email == email).first()
            if existing_user:
                logger.info(f"Found existing user with email {email}")
                return existing_user
            
            # Check if user with this username already exists
            existing_username = self.db_session.query(User).filter(User.username == username).first()
            if existing_username:
                logger.info(f"Found existing user with username {username}")
                return existing_username
            
            # Create new user if not found
            user = User(username=username, email=email)
            self.db_session.add(user)
            self.db_session.commit()
            logger.info(f"Created new user: {username}")
            return user
        except Exception as e:
            self.db_session.rollback()
            logger.error(f"Error creating/finding user: {str(e)}")
            raise

    def process_document(self, file_path: str, user_id: int) -> Dict[str, Any]:
        """Process a document and store its embeddings."""
        logger.info(f"Processing document: {file_path}")
        
        try:
            # Process document and generate embeddings
            metadata = self.document_processor.process_document(file_path, user_id)
            logger.info(f"Successfully processed document: {metadata['filename']}")
            
            return metadata
        except Exception as e:
            logger.error(f"Error processing document: {str(e)}")
            raise

    def query(self, query: str, user_id: int, k: int = 5) -> Dict[str, Any]:
        """Query the RAG system."""
        logger.info(f"Processing query: {query}")
        
        try:
            # Get user's documents
            documents = self.db_session.query(Document).filter(Document.user_id == user_id).all()
            if not documents:
                raise ValueError(f"No documents found for user {user_id}")
            
            # Generate query embedding
            query_embedding = self.embeddings.embed_query(query)
            
            # Search across all user's document indices
            all_results = []
            for doc in documents:
                results = self.document_processor.azure_search.search(
                    doc.azure_search_index,
                    query_embedding,
                    top_k=k
                )
                all_results.extend(results)
            
            # Sort results by relevance and take top k
            all_results.sort(key=lambda x: x.get("score", 0), reverse=True)
            top_results = all_results[:k]
            
            # Format results for RAG module
            formatted_results = [
                {
                    "text": result["content"],
                    "metadata": {
                        "document_id": result["document_id"],
                        "chunk_index": result["chunk_index"]
                    }
                }
                for result in top_results
            ]
            
            # Generate answer using DSPy
            answer = self.rag_module(query, formatted_results)
            
            return {
                "answer": answer,
                "sources": formatted_results
            }
        except Exception as e:
            logger.error(f"Error querying system: {str(e)}")
            raise 