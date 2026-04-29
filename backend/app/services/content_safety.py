# backend/app/services/content_safety.py
from azure.ai.contentsafety.aio import ContentSafetyClient
from azure.ai.contentsafety.models import (
    AnalyzeTextOptions,
    TextCategory,
)
from azure.core.credentials import AzureKeyCredential
from dataclasses import dataclass
from app.config import get_settings
import os
import re
import logging

logger = logging.getLogger(__name__)


@dataclass
class SafetyResult:
    """Result of content safety analysis."""
    is_flagged: bool
    categories: dict[str, int]  # category → severity (0-6)
    original_text: str


class ContentSafetyService:
    """
    Azure AI Content Safety integration.
    Provides:
    1. Text analysis for harmful content (hate, violence, self-harm, sexual)
    2. PII detection and filtering
    """

    # Severity threshold — flag content at or above this level
    SEVERITY_THRESHOLD = 2

    # PII patterns for basic regex-based filtering
    PII_PATTERNS = {
        "email": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
        "phone": r"\b(?:\+?1[-.\s]?)?(?:$?\d{3}$?[-.\s]?)?\d{3}[-.\s]?\d{4}\b",
        "ssn": r"\b\d{3}-\d{2}-\d{4}\b",
        "credit_card": r"\b(?:\d{4}[-\s]?){3}\d{4}\b",
    }

    def __init__(self):
        settings = get_settings()
        endpoint = os.environ.get(
            "AZURE_CONTENT_SAFETY_ENDPOINT",
            "https://connecta-content-safety.cognitiveservices.azure.com",
        )
        self.client = ContentSafetyClient(
            endpoint=endpoint,
            credential=AzureKeyCredential(settings.content_safety_key),
        )

    async def analyze_text(self, text: str) -> SafetyResult:
        """
        Analyze text for harmful content across 4 categories:
        - Hate
        - Violence
        - SelfHarm
        - Sexual
        
        Returns SafetyResult with is_flagged=True if any category
        exceeds SEVERITY_THRESHOLD.
        """
        try:
            request = AnalyzeTextOptions(text=text[:10000])  # API limit
            response = await self.client.analyze_text(request)

            categories = {}
            is_flagged = False

            for item in response.categories_analysis:
                severity = item.severity or 0
                categories[item.category.value] = severity
                if severity >= self.SEVERITY_THRESHOLD:
                    is_flagged = True

            if is_flagged:
                logger.warning(
                    f"Content flagged — categories: {categories}"
                )

            return SafetyResult(
                is_flagged=is_flagged,
                categories=categories,
                original_text=text,
            )

        except Exception as e:
            logger.error(f"Content safety analysis failed: {e}")
            # Fail open — return unflagged if service is down
            return SafetyResult(
                is_flagged=False,
                categories={},
                original_text=text,
            )

    async def filter_pii(self, text: str) -> str:
        """
        Remove or mask PII patterns from text.
        Uses regex-based detection for common PII types.
        """
        filtered = text
        for pii_type, pattern in self.PII_PATTERNS.items():
            matches = re.findall(pattern, filtered)
            for match in matches:
                mask = f"[{pii_type.upper()}_REDACTED]"
                filtered = filtered.replace(match, mask)
                logger.info(
                    f"Redacted {pii_type} from response"
                )

        return filtered

    async def close(self):
        """Close the async client."""
        await self.client.close()
