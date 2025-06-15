from azure.search.documents import SearchClient
from azure.core.credentials import AzureKeyCredential
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    SearchIndex,
    SimpleField,
    SearchableField,
    SearchField,
    SearchFieldDataType,
    VectorSearch,
    VectorSearchProfile,
    HnswAlgorithmConfiguration,
    HnswParameters,
    VectorSearchAlgorithmKind,
    VectorSearchAlgorithmMetric,
)
from azure.search.documents.models import VectorizedQuery
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

class AzureSearchManager:
    def __init__(self, endpoint: str, key: str):
        """Initialize Azure Search client."""
        self.endpoint = endpoint
        self.key = key
        self.credential = AzureKeyCredential(key)
        self.index_client = SearchIndexClient(endpoint=endpoint, credential=self.credential)
        
    def create_index(self, index_name: str, vector_dimensions: int = 1536) -> None:
        try:
            fields = [
                SimpleField(name="id", type=SearchFieldDataType.String, key=True),
                SearchableField(name="content", type=SearchFieldDataType.String),
                SimpleField(name="document_id", type=SearchFieldDataType.String),
                SimpleField(name="chunk_index", type=SearchFieldDataType.Int32),
                SearchField(
                    name="embedding",
                    type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
                    searchable=True,
                    vector_search_dimensions=vector_dimensions,
                    vector_search_profile_name="myHnswProfile"
                )
            ]

            vector_search = VectorSearch(
                algorithms=[
                    HnswAlgorithmConfiguration(
                        name="myHnsw",  
                        kind=VectorSearchAlgorithmKind.HNSW,
                        parameters=HnswParameters(
                            m=4,
                            ef_construction=400,
                            ef_search=500,
                            metric=VectorSearchAlgorithmMetric.COSINE
                        )
                    )
                ],
                profiles=[
                    VectorSearchProfile(
                        name="myHnswProfile",  
                        algorithm_configuration_name="myHnsw"
                    )
                ]
            )

            index = SearchIndex(
                name=index_name,
                fields=fields,
                vector_search=vector_search
            )

            self.index_client.create_or_update_index(index)
            logger.info(f"Created/updated search index: {index_name}")

        except Exception as e:
            logger.error(f"Error creating search index: {str(e)}")
            raise
            
    def upload_documents(self, index_name: str, documents: List[Dict[str, Any]]) -> None:
        """Upload documents to the search index."""
        try:
            search_client = SearchClient(
                endpoint=self.endpoint,
                index_name=index_name,
                credential=self.credential
            )
            
            # Upload documents in batches
            batch_size = 100
            for i in range(0, len(documents), batch_size):
                batch = documents[i:i + batch_size]
                search_client.upload_documents(batch)
                logger.info(f"Uploaded batch of {len(batch)} documents to index {index_name}")
                
        except Exception as e:
            logger.error(f"Error uploading documents: {str(e)}")
            raise
            
    def search(self, index_name: str, query_vector: List[float], top_k: int = 5) -> List[Dict[str, Any]]:
        """Search for similar documents using vector search."""
        try:
            search_client = SearchClient(
                endpoint=self.endpoint,
                index_name=index_name,
                credential=self.credential
            )

            vector_query = VectorizedQuery(
                vector=query_vector,
                k_nearest_neighbors=top_k,
                fields="embedding"
            )

            results = search_client.search(
                search_text="*",
                vector_queries=[vector_query],
                select=["id", "content", "document_id", "chunk_index"]
            )

            return [dict(result) for result in results]

        except Exception as e:
            logger.error(f"Error searching documents: {str(e)}")
            raise