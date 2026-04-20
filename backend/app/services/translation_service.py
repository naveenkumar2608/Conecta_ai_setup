# backend/app/services/translation_service.py
import httpx
import logging
import uuid
from app.config import get_secrets

logger = logging.getLogger(__name__)


class TranslationService:
    """
    Azure AI Translator for multi-language support.
    Supports Abbott's global field teams across different regions.
    """

    BASE_URL = "https://api.cognitive.microsofttranslator.com"
    API_VERSION = "3.0"

    # Supported languages for CONNECTA platform
    SUPPORTED_LANGUAGES = {
        "en", "es", "fr", "de", "it", "pt", "ja", "zh-Hans",
        "ko", "ar", "hi", "nl", "pl", "ru", "tr", "vi", "th",
    }

    def __init__(self):
        secrets = get_secrets()
        self.api_key = secrets.translator_key
        self.region = "eastus"  # Azure region for Translator

    async def translate(
        self,
        text: str,
        from_lang: str,
        to_lang: str,
    ) -> str:
        """
        Translate text between languages.
        
        Args:
            text: Input text to translate
            from_lang: Source language ISO code
            to_lang: Target language ISO code
            
        Returns:
            Translated text string
        """
        if from_lang == to_lang:
            return text

        if to_lang not in self.SUPPORTED_LANGUAGES:
            logger.warning(
                f"Unsupported target language: {to_lang}. "
                f"Returning original text."
            )
            return text

        url = f"{self.BASE_URL}/translate"
        params = {
            "api-version": self.API_VERSION,
            "from": from_lang,
            "to": to_lang,
        }
        headers = {
            "Ocp-Apim-Subscription-Key": self.api_key,
            "Ocp-Apim-Subscription-Region": self.region,
            "Content-Type": "application/json",
            "X-ClientTraceId": str(uuid.uuid4()),
        }
        body = [{"text": text}]

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url,
                    params=params,
                    headers=headers,
                    json=body,
                    timeout=30.0,
                )
                response.raise_for_status()

                result = response.json()
                translated = result[0]["translations"][0]["text"]

                logger.info(
                    f"Translated {len(text)} chars "
                    f"from {from_lang} to {to_lang}"
                )
                return translated

        except httpx.HTTPStatusError as e:
            logger.error(
                f"Translation API error: {e.response.status_code} "
                f"— {e.response.text}"
            )
            return text  # Fallback to original
        except Exception as e:
            logger.error(f"Translation failed: {e}")
            return text  # Fallback to original

    async def detect_language(self, text: str) -> str:
        """Detect the language of input text."""
        url = f"{self.BASE_URL}/detect"
        params = {"api-version": self.API_VERSION}
        headers = {
            "Ocp-Apim-Subscription-Key": self.api_key,
            "Ocp-Apim-Subscription-Region": self.region,
            "Content-Type": "application/json",
        }
        body = [{"text": text[:500]}]  # Use first 500 chars

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url,
                    params=params,
                    headers=headers,
                    json=body,
                    timeout=10.0,
                )
                response.raise_for_status()
                result = response.json()
                detected_lang = result[0]["language"]
                confidence = result[0]["score"]
                logger.info(
                    f"Detected language: {detected_lang} "
                    f"(confidence: {confidence})"
                )
                return detected_lang
        except Exception as e:
            logger.error(f"Language detection failed: {e}")
            return "en"  # Default to English
