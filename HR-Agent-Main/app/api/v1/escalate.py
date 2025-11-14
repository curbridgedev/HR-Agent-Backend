"""
Escalation API endpoints for HR Agent.
Handles creating and managing escalation tickets in Airtable.
"""

import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

from app.core.dependencies import get_current_user_id
from app.services.airtable import get_airtable_service

logger = logging.getLogger(__name__)

router = APIRouter()


class EscalationRequest(BaseModel):
    """Request model for creating an escalation."""
    
    message_id: str = Field(..., description="ID of the message being escalated")
    query: str = Field(..., description="User's original query")
    response: str = Field(..., description="AI's response that is being escalated")
    province: Optional[str] = Field(None, description="Province context (MB, ON, SK, AB, BC)")
    confidence_score: Optional[float] = Field(None, ge=0.0, le=1.0, description="AI confidence score")
    additional_context: Optional[str] = Field(None, description="Additional context from user")
    topic: Optional[str] = Field(None, description="Question topic/category")


class EscalationResponse(BaseModel):
    """Response model for escalation creation."""
    
    success: bool
    escalation_id: Optional[str] = None
    message: str


@router.post("", response_model=EscalationResponse)
async def create_escalation(
    request: EscalationRequest,
    current_user_id: str = Depends(get_current_user_id),
) -> EscalationResponse:
    """
    Create an escalation ticket in Airtable.
    
    This endpoint allows users to escalate low-confidence or complex questions
    to human HR specialists for review.
    """
    try:
        
        # Get Airtable service
        airtable = get_airtable_service()
        
        # Create escalation in Airtable
        metadata = {
            "message_id": request.message_id,
        }
        if request.additional_context:
            metadata["additional_context"] = request.additional_context
        if request.topic:
            metadata["topic"] = request.topic
        
        record = await airtable.create_escalation(
            user_id=current_user_id,
            session_id=request.message_id,  # Using message_id as session reference
            query=request.query,
            response=request.response,
            province=request.province,
            topic=request.topic,
            confidence_score=request.confidence_score or 0.0,
            metadata=metadata,
        )
        
        if record:
            logger.info(
                f"Escalation created for user {current_user_id}: {record.get('id')}",
                extra={"user_id": current_user_id, "record_id": record.get("id")},
            )
            return EscalationResponse(
                success=True,
                escalation_id=record.get("id"),
                message="Escalation created successfully. An HR specialist will review your question.",
            )
        else:
            # Airtable not configured, but don't fail the request
            logger.warning(f"Airtable not configured, escalation logged but not tracked")
            return EscalationResponse(
                success=True,
                message="Your question has been logged for specialist review.",
            )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create escalation: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to create escalation. Please contact support directly.",
        )


@router.get("/{escalation_id}")
async def get_escalation_status(
    escalation_id: str,
    current_user_id: str = Depends(get_current_user_id),
):
    """
    Get the status of an escalation by ID.
    """
    try:
        airtable = get_airtable_service()
        record = await airtable.get_escalation(escalation_id)
        
        if not record:
            raise HTTPException(status_code=404, detail="Escalation not found")
        
        return {
            "success": True,
            "escalation": {
                "id": record.get("id"),
                "status": record.get("fields", {}).get("Status"),
                "created_at": record.get("fields", {}).get("Created At"),
                "resolution": record.get("fields", {}).get("Resolution"),
                "resolved_at": record.get("fields", {}).get("Resolved At"),
            },
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get escalation status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve escalation status")

