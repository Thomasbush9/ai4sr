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
from langchain_community.vectorstores import FAISS
from langchain_openai import AzureOpenAIEmbeddings
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
        self.document_processor = DocumentProcessor(self.embedding_config)
        self.rag_module = RAGModule()
        self.vector_store = None
        
        # Setup directories
        self.data_dir = Path(os.getenv("DATA_DIR", "data"))
        self.index_dir = self.data_dir / "indices"
        self.data_dir.mkdir(exist_ok=True)
        self.index_dir.mkdir(exist_ok=True)
        logger.info(f"Initialized data directories: {self.data_dir}, {self.index_dir}")

    def _validate_configs(self):
        """Validate the Azure OpenAI configurations."""
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
        
        # Log configurations (excluding sensitive data)
        logger.info("Chat Configuration:")
        logger.info(f"  Endpoint: {self.chat_config['api_base']}")
        logger.info(f"  Deployment: {self.chat_config['deployment_name']}")
        logger.info(f"  API Version: {self.chat_config['api_version']}")
        
        logger.info("Embedding Configuration:")
        logger.info(f"  Endpoint: {self.embedding_config['api_base']}")
        logger.info(f"  Deployment: {self.embedding_config['deployment_name']}")
        logger.info(f"  API Version: {self.embedding_config['api_version']}")

    def process_document(self, document_path: str) -> Dict[str, Any]:
        """Process a document and store its embeddings."""
        logger.info(f"Processing document: {document_path}")
        
        try:
            # Process document and generate embeddings
            metadata = self.document_processor.process_document(
                document_path,
                str(self.index_dir / Path(document_path).stem)
            )
            
            # Save metadata
            self._save_metadata(metadata)
            logger.info(f"Successfully processed document: {metadata['filename']}")
            
            return metadata
        except Exception as e:
            logger.error(f"Error processing document: {str(e)}")
            raise

    def query(self, query: str, k: int = 5) -> Dict[str, Any]:
        """Query the RAG system."""
        logger.info(f"Processing query: {query}")
        
        try:
            # Load vector store
            if not self.vector_store:
                self._load_vector_store()
            
            # Retrieve relevant chunks
            relevant_chunks = self._retrieve_chunks(query, k)
            
            # Generate answer using DSPy
            answer = self.rag_module(query, relevant_chunks)
            
            return {
                "answer": answer,
                "sources": relevant_chunks
            }
        except Exception as e:
            logger.error(f"Error querying system: {str(e)}")
            raise

    def _save_metadata(self, metadata: Dict[str, Any]):
        """Save document metadata."""
        metadata_path = self.data_dir / f"{metadata['filename']}_metadata.json"
        with open(metadata_path, "w") as f:
            json.dump(metadata, f, indent=2)
        logger.info(f"Saved metadata to: {metadata_path}")

    def _load_vector_store(self):
        """Load the vector store from disk."""
        logger.info("Loading vector store...")
        
        try:
            embeddings = AzureOpenAIEmbeddings(
                model=self.embedding_config["deployment_name"],
                azure_endpoint=self.embedding_config["api_base"],
                api_key=self.embedding_config["api_key"],
                api_version=self.embedding_config["api_version"]
            )
            
            # Load all indices
            indices = [f for f in self.index_dir.glob("*") if f.is_dir()]

            if not indices:
                error_msg = "No vector indices found. Please process some documents first."
                logger.error(error_msg)
                raise ValueError(error_msg)
            
            # Load the first index with deserialization allowed
            self.vector_store = FAISS.load_local(
                str(indices[0]), 
                embeddings,
                allow_dangerous_deserialization=True  # Safe since we created these indices
            )
            logger.info(f"Loaded initial index from: {indices[0]}")
            
            # Merge other indices if they exist
            for index_path in indices[1:]:
                other_store = FAISS.load_local(
                    str(index_path), 
                    embeddings,
                    allow_dangerous_deserialization=True  # Safe since we created these indices
                )
                self.vector_store.merge_from(other_store)
                logger.info(f"Merged index from: {index_path}")
                
        except Exception as e:
            logger.error(f"Error loading vector store: {str(e)}")
            raise

    def _retrieve_chunks(self, query: str, k: int) -> List[Dict[str, Any]]:
        """Retrieve relevant chunks for a query."""
        if not self.vector_store:
            self._load_vector_store()
        
        # Retrieve documents
        docs = self.vector_store.similarity_search(query, k=k)
        logger.info(f"Retrieved {len(docs)} chunks for query")
        
        # Format results
        return [{"text": doc.page_content, "metadata": doc.metadata} for doc in docs] 