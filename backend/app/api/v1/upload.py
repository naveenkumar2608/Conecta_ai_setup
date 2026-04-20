# backend/app/api/v1/upload.py
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from app.models.api_models import UploadResponse, UploadStatusResponse
from app.repositories.blob_repo import BlobRepository
from app.repositories.postgres_repo import PostgresRepository
from app.dependencies import (
    get_blob_repo, get_postgres_repo, get_current_user
)
from app.models.api_models import UserContext
import uuid
from datetime import datetime, timezone

router = APIRouter()


@router.post("/csv", response_model=UploadResponse)
async def upload_csv(
    file: UploadFile = File(...),
    user: UserContext = Depends(get_current_user),
    blob_repo: BlobRepository = Depends(get_blob_repo),
    postgres_repo: PostgresRepository = Depends(get_postgres_repo),
):
    """
    Upload a CSV file for ingestion.
    
    Flow:
    1. Validate file type and size
    2. Generate unique blob name
    3. Upload to Azure Blob Storage (csv-uploads container)
    4. Create ingestion record in PostgreSQL (status: pending)
    5. Return upload ID for status tracking
    
    Note: Actual processing is handled by Azure Function blob trigger.
    """
    # Validate
    if not file.filename.endswith(".csv"):
        raise HTTPException(
            status_code=400, detail="Only CSV files are accepted."
        )
    
    if file.size and file.size > 50 * 1024 * 1024:  # 50MB limit
        raise HTTPException(
            status_code=400, detail="File size exceeds 50MB limit."
        )

    # Generate unique identifiers
    upload_id = str(uuid.uuid4())
    blob_name = f"{user.user_id}/{upload_id}/{file.filename}"
    
    try:
        # Read file content
        content = await file.read()
        
        # Upload to Blob Storage
        blob_url = await blob_repo.upload_blob(
            container_name="csv-uploads",
            blob_name=blob_name,
            data=content,
            content_type="text/csv",
            metadata={
                "upload_id": upload_id,
                "user_id": user.user_id,
                "original_filename": file.filename,
            },
        )
        
        # Create ingestion record
        await postgres_repo.insert_file_metadata(
            upload_id=upload_id,
            user_id=user.user_id,
            file_name=file.filename,
            blob_url=blob_url,
            blob_name=blob_name,
            file_size_bytes=len(content),
            status="pending",
            uploaded_at=datetime.now(timezone.utc),
        )

        return UploadResponse(
            upload_id=upload_id,
            file_name=file.filename,
            status="pending",
            message="File uploaded successfully. Processing will begin shortly.",
        )

    except Exception as e:
        # Log error and clean up
        raise HTTPException(
            status_code=500, 
            detail=f"Upload failed: {str(e)}"
        )


@router.get("/status/{upload_id}", response_model=UploadStatusResponse)
async def get_upload_status(
    upload_id: str,
    user: UserContext = Depends(get_current_user),
    postgres_repo: PostgresRepository = Depends(get_postgres_repo),
):
    """Get the ingestion status of an uploaded CSV file."""
    record = await postgres_repo.get_file_metadata(
        upload_id=upload_id, user_id=user.user_id
    )
    if not record:
        raise HTTPException(status_code=404, detail="Upload not found.")
    
    return UploadStatusResponse(
        upload_id=record.upload_id,
        file_name=record.file_name,
        status=record.status,
        row_count=record.row_count,
        chunk_count=record.chunk_count,
        error_message=record.error_message,
        started_at=record.processing_started_at,
        completed_at=record.processing_completed_at,
    )
