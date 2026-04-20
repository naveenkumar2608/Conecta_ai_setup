# backend/app/services/chat_service.py
from langchain_core.messages import HumanMessage
from app.agents.graph import CoachingGraphBuilder
from app.agents.state import AgentState
from app.services.cache_service import CacheService
from app.services.translation_service import TranslationService
from app.repositories.postgres_repo import PostgresRepository
from app.models.api_models import ChatResult
from datetime import datetime, timezone
import uuid
import logging

logger = logging.getLogger(__name__)


class ChatService:
    """
    Orchestrates the full chat pipeline:
    1. Cache check
    2. Translation (if needed)
    3. LangGraph execution
    4. Response caching
    5. Conversation persistence
    """

    def __init__(
        self,
        graph: CoachingGraphBuilder,
        cache_service: CacheService,
        translation_service: TranslationService,
        postgres_repo: PostgresRepository,
    ):
        self.compiled_graph = graph.build()
        self.cache = cache_service
        self.translator = translation_service
        self.db = postgres_repo

    async def process_chat(
        self,
        user_id: str,
        session_id: str | None,
        message: str,
        language: str = "en",
    ) -> ChatResult:
        """Process a chat message through the multi-agent system."""
        
        # Generate session ID if new conversation
        if not session_id:
            session_id = str(uuid.uuid4())

        # ── Step 1: Check cache ──────────────────────────────
        cache_key = f"chat:{user_id}:{hash(message)}"
        cached_response = await self.cache.get(cache_key)
        if cached_response:
            logger.info(f"Cache hit for user {user_id}")
            return ChatResult.model_validate_json(cached_response)

        # ── Step 2: Translate if needed ──────────────────────
        translated_message = message
        if language != "en":
            translated_message = await self.translator.translate(
                text=message, 
                from_lang=language, 
                to_lang="en"
            )

        # ── Step 3: Load conversation history from Redis/DB ──
        history = await self._load_history(user_id, session_id)

        # ── Step 4: Build initial state ──────────────────────
        initial_state: AgentState = {
            "messages": history + [
                HumanMessage(content=translated_message)
            ],
            "user_id": user_id,
            "session_id": session_id,
            "language": language,
            "intent": None,
            "retrieved_documents": None,
            "coaching_response": None,
            "analytics_result": None,
            "recommendation": None,
            "search_query": translated_message,
            "top_k_results": None,
            "next_agent": None,
            "requires_safety_check": False,
            "iteration_count": 0,
            "error": None,
            "final_response": None,
        }

        # ── Step 5: Execute LangGraph ────────────────────────
        config = {
            "configurable": {
                "thread_id": session_id
            }
        }
        
        final_state = await self.compiled_graph.ainvoke(
            initial_state, config=config
        )

        # ── Step 6: Translate response back if needed ────────
        response_text = final_state.get(
            "final_response", 
            "I couldn't process your request. Please try again."
        )
        if language != "en":
            response_text = await self.translator.translate(
                text=response_text, 
                from_lang="en", 
                to_lang=language
            )

        # ── Step 7: Build result ─────────────────────────────
        sources = []
        if final_state.get("top_k_results"):
            sources = [
                {
                    "file_name": d.get("file_name", ""),
                    "relevance_score": d.get("reranker_score", 0),
                }
                for d in final_state["top_k_results"][:3]
            ]

        result = ChatResult(
            session_id=session_id,
            message=response_text,
            intent=final_state.get("intent", "unknown"),
            sources=sources,
            metadata={
                "agent_path": self._get_agent_path(final_state),
                "iteration_count": final_state.get(
                    "iteration_count", 0
                ),
            },
        )

        # ── Step 8: Cache response ───────────────────────────
        await self.cache.set(
            cache_key, result.model_dump_json(), ttl=600
        )

        # ── Step 9: Persist conversation ─────────────────────
        await self.db.save_message(
            session_id=session_id,
            user_id=user_id,
            role="user",
            content=message,
            timestamp=datetime.now(timezone.utc),
        )
        await self.db.save_message(
            session_id=session_id,
            user_id=user_id,
            role="assistant",
            content=response_text,
            intent=final_state.get("intent"),
            timestamp=datetime.now(timezone.utc),
        )

        return result

    async def process_chat_stream(
        self,
        user_id: str,
        session_id: str | None,
        message: str,
        language: str = "en",
    ):
        """Streaming version — yields chunks via LangGraph astream."""
        if not session_id:
            session_id = str(uuid.uuid4())

        translated_message = message
        if language != "en":
            translated_message = await self.translator.translate(
                text=message, from_lang=language, to_lang="en"
            )

        history = await self._load_history(user_id, session_id)

        initial_state: AgentState = {
            "messages": history + [
                HumanMessage(content=translated_message)
            ],
            "user_id": user_id,
            "session_id": session_id,
            "language": language,
            "intent": None,
            "retrieved_documents": None,
            "coaching_response": None,
            "analytics_result": None,
            "recommendation": None,
            "search_query": translated_message,
            "top_k_results": None,
            "next_agent": None,
            "requires_safety_check": False,
            "iteration_count": 0,
            "error": None,
            "final_response": None,
        }

        config = {"configurable": {"thread_id": session_id}}

        async for event in self.compiled_graph.astream_events(
            initial_state, config=config, version="v2"
        ):
            if event["event"] == "on_chat_model_stream":
                chunk = event["data"]["chunk"]
                if hasattr(chunk, "content") and chunk.content:
                    yield {
                        "type": "content",
                        "content": chunk.content,
                        "node": event.get("name", ""),
                    }
            elif event["event"] == "on_chain_end":
                if event.get("name") == "supervisor":
                    output = event.get("data", {}).get("output", {})
                    yield {
                        "type": "routing",
                        "intent": output.get("intent", ""),
                        "agent": output.get("next_agent", ""),
                    }

    async def _load_history(
        self, user_id: str, session_id: str
    ) -> list:
        """Load conversation history from cache or DB."""
        cache_key = f"history:{user_id}:{session_id}"
        cached = await self.cache.get(cache_key)
        if cached:
            import json
            messages_data = json.loads(cached)
            return [
                HumanMessage(content=m["content"])
                if m["role"] == "user"
                else HumanMessage(content=m["content"])  
                # Simplified — in production, use AIMessage for assistant
                for m in messages_data
            ]
        
        db_messages = await self.db.get_session_messages(
            session_id=session_id, user_id=user_id
        )
        return db_messages or []

    @staticmethod
    def _get_agent_path(state: AgentState) -> str:
        """Extract the agent execution path from messages."""
        path = []
        for msg in state.get("messages", []):
            if hasattr(msg, "name") and msg.name:
                path.append(msg.name)
        return " → ".join(path)
