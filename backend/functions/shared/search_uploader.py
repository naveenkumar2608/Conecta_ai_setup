# functions/shared/search_uploader.py
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    SearchIndex,
    SearchField,
    SearchFieldDataType,
    VectorSearch,
    HnswAlgorithmConfiguration,
    VectorSearchProfile,
    SemanticConfiguration,
    SemanticSearch,
    SemanticPrioritizedFields,
    SemanticField,
    SearchableField,
    SimpleField,
    SearchIndex,
)
from azure.core.credentials import AzureKeyCredential
import logging
import math

logger = logging.getLogger(__name__)


class SearchUploader:
    """Upload embedded chunks to Azure AI Search index."""

    def __init__(
        self,
        endpoint: str,
        api_key: str,
        index_name: str,
        embedding_dimensions: int = 3072,
    ):
        self.credential = AzureKeyCredential(api_key)
        self.endpoint = endpoint
        self.index_name = index_name
        self.embedding_dimensions = embedding_dimensions
        
        self.index_client = SearchIndexClient(
            endpoint=endpoint, credential=self.credential
        )
        self.search_client = SearchClient(
            endpoint=endpoint,
            index_name=index_name,
            credential=self.credential,
        )

    def ensure_index_exists(self):
        """Create the search index if it doesn't exist."""
        try:
            self.index_client.get_index(self.index_name)
            logger.info(f"Index '{self.index_name}' already exists")
        except Exception:
            logger.info(f"Creating index '{self.index_name}'")
            self._create_index()

    def _create_index(self):
        """Create Azure AI Search index with vector + semantic config."""
        fields = [
            SimpleField(
                name="chunk_id",
                type=SearchFieldDataType.String,
                key=True,
                filterable=True,
            ),
            SearchableField(
                name="chunk_text",
                type=SearchFieldDataType.String,
                analyzer_name="en.microsoft",
            ),
            SearchField(
                name="embedding",
                type=SearchFieldDataType.Collection(
                    SearchFieldDataType.Single
                ),
                searchable=True,
                vector_search_dimensions=self.embedding_dimensions,
                vector_search_profile_name="connecta-vector-profile",
            ),
            SimpleField(
                name="file_name",
                type=SearchFieldDataType.String,
                filterable=True,
                facetable=True,
            ),
            SimpleField(
                name="upload_id",
                type=SearchFieldDataType.String,
                filterable=True,
            ),
            SimpleField(
                name="user_id",
                type=SearchFieldDataType.String,
                filterable=True,
            ),
            SimpleField(
                name="row_start",
                type=SearchFieldDataType.Int32,
                filterable=True,
            ),
            SimpleField(
                name="row_end",
                type=SearchFieldDataType.Int32,
                filterable=True,
            ),
            SearchableField(
                name="domain_tags",
                type=SearchFieldDataType.Collection(
                    SearchFieldDataType.String
                ),
                filterable=True,
                facetable=True,
            ),
            SimpleField(
                name="upload_time",
                type=SearchFieldDataType.DateTimeOffset,
                filterable=True,
                sortable=True,
            ),
            SearchableField(
                name="column_names",
                type=SearchFieldDataType.Collection(
                    SearchFieldDataType.String
                ),
                filterable=True,
            ),
        ]

        vector_search = VectorSearch(
            algorithms=[
                HnswAlgorithmConfiguration(
                    name="connecta-hnsw-config",
                    parameters={
                        "m": 4,
                        "efConstruction": 400,
                        "efSearch": 500,
                        "metric": "cosine",
                    },
                )
            ],
            profiles=[
                VectorSearchProfile(
                    name="connecta-vector-profile",
                    algorithm_configuration_name="connecta-hnsw-config",
                )
            ],
        )

        semantic_config = SemanticConfiguration(
            name="connecta-semantic-config",
            prioritized_fields=SemanticPrioritizedFields(
                content_fields=[
                    SemanticField(field_name="chunk_text")
                ],
                keywords_fields=[
                    SemanticField(field_name="domain_tags")
                ],
                title_field=SemanticField(field_name="file_name"),
            ),
        )

        index = SearchIndex(
            name=self.index_name,
            fields=fields,
            vector_search=vector_search,
            semantic_search=SemanticSearch(
                configurations=[semantic_config]
            ),
        )

        self.index_client.create_or_update_index(index)
        logger.info(f"Created index: {self.index_name}")

    async def upload_documents(
        self, 
        embedded_chunks: list[dict],
        batch_size: int = 100,
    ):
        """Upload embedded chunks to Azure AI Search in batches."""
        self.ensure_index_exists()
        
        total_batches = math.ceil(len(embedded_chunks) / batch_size)
        
        for batch_idx in range(0, len(embedded_chunks), batch_size):
            batch = embedded_chunks[
                batch_idx : batch_idx + batch_size
            ]
            
            # Format documents for upload
            documents = []
            for chunk in batch:
                doc = {
                    "chunk_id": chunk["chunk_id"],
                    "chunk_text": chunk["chunk_text"],
                    "embedding": chunk["embedding"],
                    "file_name": chunk["file_name"],
                    "upload_id": chunk["upload_id"],
                    "user_id": chunk["user_id"],
                    "row_start": chunk["row_start"],
                    "row_end": chunk["row_end"],
                    "domain_tags": chunk.get("domain_tags", []),
                    "upload_time": chunk["upload_time"],
                    "column_names": chunk.get("column_names", []),
                }
                documents.append(doc)

            current = batch_idx // batch_size + 1
            logger.info(
                f"Uploading batch {current}/{total_batches} "
                f"({len(documents)} docs)"
            )
            
            result = self.search_client.upload_documents(
                documents=documents
            )
            
            # Check for failures
            failed = [
                r for r in result if not r.succeeded
            ]
            if failed:
                logger.error(
                    f"Failed to upload {len(failed)} documents: "
                    f"{[f.key for f in failed]}"
                )

        logger.info(
            f"Uploaded {len(embedded_chunks)} documents to "
            f"index '{self.index_name}'"
        )
