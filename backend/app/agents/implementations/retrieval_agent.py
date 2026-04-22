from langchain_core.messages import AIMessage
from app.agents.state import AgentState
from app.services.search_service import SearchService
from app.services.embedding_service import EmbeddingService
from app.services.analytics_service import AnalyticsService


class RetrievalAgent:
    """
    Unified Retrieval Agent

    Fetches data from:
    - Azure AI Search (unstructured / documents)
    - PostgreSQL (structured / tabular)

    Output:
        - state.top_k_results
        - state.agent_outputs["retrieval"]
    """

    def __init__(
        self,
        search_service: SearchService,
        embedding_service: EmbeddingService,
        analytics_service: AnalyticsService,
    ):
        self.search_service = search_service
        self.embedding_service = embedding_service
        self.analytics_service = analytics_service

    async def retrieve(self, state: AgentState) -> AgentState:
        query = state.get("search_query")

        if not query:
            return {
                **state,
                "error": "Search query missing",
            }

        # ─────────────────────────────────────────────
        # 1. Azure AI Search Retrieval
        # ─────────────────────────────────────────────
        query_vector = await self.embedding_service.generate_embedding(query)

        search_results = await self.search_service.hybrid_search(
            query_text=query,
            query_vector=query_vector,
            top_k=5,
            semantic_configuration="connecta-semantic-config",
            select_fields=[
                "chunk_text",
                "file_name",
                "domain_tags",
                "row_index",
                "upload_time",
            ],
        )

        document_results = [
            {
                "type": "document",
                "content": result["chunk_text"],
                "source": result.get("file_name", ""),
                "score": result.get("@search.score", 0),
            }
            for result in search_results
        ]

        # ─────────────────────────────────────────────
        # 2. PostgreSQL Retrieval (LIGHTWEIGHT CONTEXT)
        # ─────────────────────────────────────────────

        structured_results = []

        try:
            # Example: fetch recent coaching summaries
            db_data = await self.analytics_service.fetch_recent_activity(
                user_id=state["user_id"]
            )

            for row in db_data:
                structured_results.append({
                    "type": "structured",
                    "content": str(row),
                    "source": "postgres",
                })

        except Exception:
            # Do not break flow if DB fails
            structured_results = []

        # ─────────────────────────────────────────────
        # 3. Combine Results
        # ─────────────────────────────────────────────
        combined_results = document_results + structured_results

        # Limit final results
        top_results = combined_results[:5]

        # ─────────────────────────────────────────────
        # 4. Update agent_outputs
        # ─────────────────────────────────────────────
        agent_outputs = state.get("agent_outputs") or {}
        agent_outputs["retrieval"] = top_results

        return {
            **state,
            "top_k_results": top_results,
            "agent_outputs": agent_outputs,
            "messages": state["messages"] + [
                AIMessage(
                    content=f"Retrieved {len(combined_results)} items from search and database.",
                    name="retrieval_agent"
                )
            ],
        }