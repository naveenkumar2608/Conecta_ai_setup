# backend/app/agents/retrieval_agent.py
from langchain_core.messages import AIMessage
from app.agents.state import AgentState
from app.services.search_service import SearchService
from app.services.embedding_service import EmbeddingService


class RetrievalAgent:
    """
    Role: Vector + semantic search over Azure AI Search indices.
    Input: state.search_query (user's natural language query)
    Output: state.retrieved_documents, state.top_k_results
    Tools: 
        - Azure OpenAI Embeddings (text-embedding-3-large) for query vectorization
        - Azure AI Search (vector + semantic hybrid search)
    LangGraph node logic: 
        1. Generate embedding for user query
        2. Execute hybrid search (vector + keyword + semantic reranker)
        3. Return top-k documents with metadata
        4. Populate state with results for downstream agents
    """

    def __init__(
        self, 
        search_service: SearchService, 
        embedding_service: EmbeddingService
    ):
        self.search_service = search_service
        self.embedding_service = embedding_service

    async def retrieve(self, state: AgentState) -> AgentState:
        """LangGraph node function — performs RAG retrieval."""
        query = state["search_query"]

        # Step 1: Generate query embedding
        query_vector = await self.embedding_service.generate_embedding(query)

        # Step 2: Hybrid search (vector + semantic + keyword)
        search_results = await self.search_service.hybrid_search(
            query_text=query,
            query_vector=query_vector,
            top_k=10,
            semantic_configuration="connecta-semantic-config",
            select_fields=[
                "chunk_text", "file_name", "domain_tags", 
                "row_index", "upload_time"
            ],
        )

        # Step 3: Format results
        retrieved_docs = []
        for result in search_results:
            retrieved_docs.append({
                "content": result["chunk_text"],
                "file_name": result.get("file_name", ""),
                "domain_tags": result.get("domain_tags", []),
                "score": result.get("@search.score", 0),
                "reranker_score": result.get(
                    "@search.reranker_score", 0
                ),
            })

        # Step 4: Build context string for downstream agents
        context_str = "\n\n---\n\n".join(
            [
                f"[Source: {d['file_name']}] "
                f"(Relevance: {d['reranker_score']:.2f})\n{d['content']}"
                for d in retrieved_docs[:5]
            ]
        )

        return {
            **state,
            "retrieved_documents": retrieved_docs,
            "top_k_results": retrieved_docs[:5],
            "messages": state["messages"] + [
                AIMessage(
                    content=f"Retrieved {len(retrieved_docs)} relevant documents.",
                    name="retrieval_agent"
                )
            ],
        }
