from rag_system import RAGSystem
import os
from dotenv import load_dotenv
import logging
import sys
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

def main():
    # Load environment variables
    load_dotenv()

    # Print environment variables (excluding sensitive data)
    logger.info("Checking environment variables...")
    required_vars = [
        "AZURE_OPENAI_ENDPOINT",
        "AZURE_OPENAI_DEPLOYMENT_NAME",
        "AZURE_OPENAI_API_VERSION"
    ]
    for var in required_vars:
        value = os.getenv(var)
        if value:
            logger.info(f"{var} is set")
        else:
            logger.error(f"{var} is not set")

    # Initialize RAG system
    try:
        rag = RAGSystem()
    except Exception as e:
        logger.error(f"Failed to initialize RAG system: {str(e)}")
        return

    # Load file paths from .env or default to Docker volume paths
    download_dir = Path(os.getenv("DOWNLOAD_DIR", "/app/downloads"))
    filename = "hopfield-2009-neurodynamics-of-mental-exploration.pdf"
    document_path = download_dir / filename

    try:
        logger.info(f"Processing document: {document_path}")
        metadata = rag.process_document(document_path)
        logger.info(f"Successfully processed document: {metadata['filename']}")
        logger.info(f"Number of chunks: {metadata['num_chunks']}")
    except Exception as e:
        logger.error(f"Error processing document: {str(e)}")
        return
    
    # Example: Query the system
    query = "What is the main topic of the document?"
    try:
        logger.info(f"Processing query: {query}")
        result = rag.query(query)
        logger.info("\nQuery: " + query)
        logger.info("\nAnswer: " + result["answer"])
        logger.info("\nSources:")
        for i, source in enumerate(result["sources"], 1):
            logger.info(f"\nSource {i}:")
            logger.info(source["text"][:200] + "...")  # Print first 200 chars of each source
    except Exception as e:
        logger.error(f"Error querying system: {str(e)}")

if __name__ == "__main__":
    main() 