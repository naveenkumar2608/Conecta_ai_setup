# backend/app/services/service_bus_client.py
from azure.servicebus.aio import ServiceBusClient
from azure.servicebus import ServiceBusMessage
from app.config import get_secrets
import json
import logging

logger = logging.getLogger(__name__)


class ServiceBusPublisher:
    """
    Azure Service Bus publisher for async event-driven messaging.
    
    Used for:
    - Ingestion status notifications
    - Async analytics computation triggers
    - Cross-service event communication
    """

    def __init__(self):
        secrets = get_secrets()
        self.connection_string = secrets.service_bus_connection_string
        self._client: ServiceBusClient | None = None

    async def _get_client(self) -> ServiceBusClient:
        if self._client is None:
            self._client = ServiceBusClient.from_connection_string(
                self.connection_string
            )
        return self._client

    async def publish_message(
        self,
        queue_name: str,
        message_body: dict,
        subject: str | None = None,
        correlation_id: str | None = None,
        session_id: str | None = None,
    ):
        """
        Publish a message to a Service Bus queue.
        
        Args:
            queue_name: Target queue (e.g., "ingestion-status", "analytics-jobs")
            message_body: Dict payload (will be JSON serialized)
            subject: Message subject for filtering
            correlation_id: For request-reply patterns
            session_id: For ordered message processing
        """
        client = await self._get_client()

        try:
            async with client.get_queue_sender(queue_name) as sender:
                message = ServiceBusMessage(
                    body=json.dumps(message_body),
                    subject=subject,
                    correlation_id=correlation_id,
                    session_id=session_id,
                    content_type="application/json",
                    application_properties={
                        "source": "connecta-backend",
                        "version": "1.0",
                    },
                )
                await sender.send_messages(message)
                logger.info(
                    f"Published message to '{queue_name}': "
                    f"subject={subject}, "
                    f"correlation_id={correlation_id}"
                )

        except Exception as e:
            logger.error(
                f"Failed to publish to '{queue_name}': {e}"
            )
            raise

    async def publish_ingestion_event(
        self,
        upload_id: str,
        status: str,
        user_id: str,
        file_name: str,
        details: dict | None = None,
    ):
        """Convenience method for ingestion status events."""
        await self.publish_message(
            queue_name="ingestion-status",
            message_body={
                "event_type": "ingestion_status_changed",
                "upload_id": upload_id,
                "status": status,
                "user_id": user_id,
                "file_name": file_name,
                "details": details or {},
            },
            subject=f"ingestion.{status}",
            correlation_id=upload_id,
        )

    async def publish_analytics_job(
        self,
        upload_id: str,
        user_id: str,
        job_type: str = "full_compute",
    ):
        """Trigger an async analytics computation job."""
        await self.publish_message(
            queue_name="analytics-jobs",
            message_body={
                "event_type": "analytics_job_requested",
                "upload_id": upload_id,
                "user_id": user_id,
                "job_type": job_type,
            },
            subject=f"analytics.{job_type}",
            correlation_id=upload_id,
        )

    async def close(self):
        """Close the Service Bus client."""
        if self._client:
            await self._client.close()
            self._client = None