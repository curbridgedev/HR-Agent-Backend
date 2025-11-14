"""
Airtable Integration Service for HR Agent Escalations
Handles creating and managing escalation tickets in Airtable
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx
from app.core.config import settings

logger = logging.getLogger(__name__)


class AirtableService:
    """Service for interacting with Airtable API for escalation management"""

    def __init__(self):
        self.base_url = "https://api.airtable.com/v0"
        self.base_id = settings.airtable_base_id
        self.api_key = settings.airtable_api_key
        self.escalations_table = settings.airtable_escalations_table or "Escalations"
        
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def create_escalation(
        self,
        user_id: str,
        session_id: str,
        query: str,
        response: str,
        province: Optional[str] = None,
        topic: Optional[str] = None,
        confidence_score: float = 0.0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Create an escalation ticket in Airtable.

        Args:
            user_id: User who initiated the escalation
            session_id: Chat session ID
            query: Original user query
            response: AI response that was escalated
            province: Province context (MB, ON, SK, AB, BC)
            topic: Topic/category of the question
            confidence_score: AI confidence score
            metadata: Additional metadata

        Returns:
            Airtable record data if successful, None otherwise
        """
        try:
            if not self.base_id or not self.api_key:
                logger.warning("Airtable credentials not configured, skipping escalation")
                return None

            # Prepare record data
            fields = {
                "User ID": user_id,
                "Session ID": session_id,
                "Query": query,
                "AI Response": response,
                "Confidence Score": confidence_score,
                "Status": "New",
                "Created At": datetime.utcnow().isoformat(),
            }

            # Optional fields
            if province:
                fields["Province"] = province
            if topic:
                fields["Topic"] = topic
            if metadata:
                fields["Metadata"] = str(metadata)

            # Create record
            url = f"{self.base_url}/{self.base_id}/{self.escalations_table}"
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    url,
                    headers=self.headers,
                    json={"fields": fields},
                )
                response.raise_for_status()
                
                record = response.json()
                logger.info(f"Escalation created in Airtable: {record['id']}")
                return record

        except httpx.HTTPError as e:
            logger.error(f"Failed to create Airtable escalation: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error creating escalation: {e}")
            return None

    async def get_escalation(self, record_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve an escalation record by ID.

        Args:
            record_id: Airtable record ID

        Returns:
            Record data if found, None otherwise
        """
        try:
            url = f"{self.base_url}/{self.base_id}/{self.escalations_table}/{record_id}"
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url, headers=self.headers)
                response.raise_for_status()
                return response.json()

        except httpx.HTTPError as e:
            logger.error(f"Failed to get escalation {record_id}: {e}")
            return None

    async def update_escalation_status(
        self,
        record_id: str,
        status: str,
        resolution: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Update the status of an escalation.

        Args:
            record_id: Airtable record ID
            status: New status (New, In Progress, Resolved, Closed)
            resolution: Resolution notes

        Returns:
            Updated record data if successful, None otherwise
        """
        try:
            url = f"{self.base_url}/{self.base_id}/{self.escalations_table}/{record_id}"
            
            fields = {"Status": status}
            if resolution:
                fields["Resolution"] = resolution
                fields["Resolved At"] = datetime.utcnow().isoformat()

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.patch(
                    url,
                    headers=self.headers,
                    json={"fields": fields},
                )
                response.raise_for_status()
                return response.json()

        except httpx.HTTPError as e:
            logger.error(f"Failed to update escalation {record_id}: {e}")
            return None

    async def list_escalations(
        self,
        status: Optional[str] = None,
        province: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        List escalations with optional filters.

        Args:
            status: Filter by status
            province: Filter by province
            limit: Maximum number of records to return

        Returns:
            List of escalation records
        """
        try:
            url = f"{self.base_url}/{self.base_id}/{self.escalations_table}"
            
            params = {"maxRecords": limit}
            
            # Build filter formula
            filters = []
            if status:
                filters.append(f"{{Status}}='{status}'")
            if province:
                filters.append(f"{{Province}}='{province}'")
            
            if filters:
                params["filterByFormula"] = f"AND({','.join(filters)})"

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url, headers=self.headers, params=params)
                response.raise_for_status()
                
                data = response.json()
                return data.get("records", [])

        except httpx.HTTPError as e:
            logger.error(f"Failed to list escalations: {e}")
            return []

    async def track_analytics_event(
        self,
        event_type: str,
        province: Optional[str] = None,
        topic: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Track analytics events in Airtable (queries, resolutions, etc.).

        Args:
            event_type: Type of event (query, resolution, feedback)
            province: Province context
            topic: Topic/category
            metadata: Additional event data

        Returns:
            Airtable record if successful, None otherwise
        """
        try:
            analytics_table = settings.airtable_analytics_table or "Analytics"
            
            fields = {
                "Event Type": event_type,
                "Timestamp": datetime.utcnow().isoformat(),
            }
            
            if province:
                fields["Province"] = province
            if topic:
                fields["Topic"] = topic
            if metadata:
                fields["Metadata"] = str(metadata)

            url = f"{self.base_url}/{self.base_id}/{analytics_table}"
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    url,
                    headers=self.headers,
                    json={"fields": fields},
                )
                response.raise_for_status()
                return response.json()

        except httpx.HTTPError as e:
            logger.error(f"Failed to track analytics event: {e}")
            return None


# Singleton instance
_airtable_service: Optional[AirtableService] = None


def get_airtable_service() -> AirtableService:
    """Get or create the Airtable service singleton."""
    global _airtable_service
    if _airtable_service is None:
        _airtable_service = AirtableService()
    return _airtable_service

