"""
File Management API Router

World-class file upload, download, streaming, and management endpoints.
"""

from uuid import UUID
from typing import Optional, List
from fastapi import APIRouter, Depends, UploadFile, File as FastAPIFile, HTTPException, Response, Query
from fastapi.responses import StreamingResponse, FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel as PydanticModel
from datetime import datetime
import io

from velvetecho.database import get_session
from velvetecho.files.manager import FileManager
from velvetecho.files.models import File, Folder
from velvetecho.files.storage import LocalStorage, S3Storage
from velvetecho.api import StandardResponse, PaginatedResponse
from velvetecho.api.exceptions import NotFoundException

# Router configuration
PREFIX = "/api/files"
TAGS = ["Files"]

router = APIRouter()

# ============================================================================
# Pydantic Schemas
# ============================================================================


class FileUploadResponse(PydanticModel):
    """File upload response"""
    id: UUID
    name: str
    size: int
    mime_type: str
    url: str

    class Config:
        from_attributes = True


class FileResponse(PydanticModel):
    """File metadata response"""
    id: UUID
    name: str
    original_name: str
    mime_type: str
    size: int
    size_human: str
    extension: Optional[str]
    folder_id: Optional[UUID]
    owner_id: str
    workspace_id: Optional[UUID]
    has_thumbnail: bool
    is_public: bool
    access_count: int
    created_at: datetime
    updated_at: datetime
    is_image: bool
    is_video: bool
    is_audio: bool
    is_document: bool

    class Config:
        from_attributes = True


class FolderCreate(PydanticModel):
    """Create folder request"""
    name: str
    parent_id: Optional[UUID] = None
    workspace_id: Optional[UUID] = None
    description: Optional[str] = None


class FolderResponse(PydanticModel):
    """Folder response"""
    id: UUID
    name: str
    path: str
    parent_id: Optional[UUID]
    owner_id: str
    workspace_id: Optional[UUID]
    description: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class FileMoveRequest(PydanticModel):
    """Move file request"""
    folder_id: Optional[UUID] = None


class FileSearchRequest(PydanticModel):
    """File search request"""
    query: str
    workspace_id: Optional[UUID] = None
    mime_type: Optional[str] = None
    limit: int = 50


# ============================================================================
# Dependencies
# ============================================================================


def get_file_manager(session: AsyncSession = Depends(get_session)) -> FileManager:
    """Get file manager instance"""
    # TODO: Make storage backend configurable via environment
    storage = LocalStorage("./storage/files")
    return FileManager(session, storage)


# ============================================================================
# File Upload Endpoints
# ============================================================================


@router.post("/upload", response_model=StandardResponse[FileUploadResponse], status_code=201)
async def upload_file(
    file: UploadFile = FastAPIFile(...),
    folder_id: Optional[UUID] = Query(None),
    workspace_id: Optional[UUID] = Query(None),
    manager: FileManager = Depends(get_file_manager),
):
    """
    Upload a single file

    Supports all file types with automatic:
    - MIME type detection
    - MD5/SHA256 hashing
    - Metadata extraction
    - Storage organization

    Example:
        curl -X POST http://localhost:8000/api/files/upload \\
            -F "file=@document.pdf" \\
            -F "folder_id=uuid" \\
            -F "workspace_id=uuid"
    """
    try:
        # Read file content
        file_data = await file.read()
        file_obj = io.BytesIO(file_data)

        # Upload file
        uploaded_file = await manager.upload_file(
            file_data=file_obj,
            filename=file.filename,
            folder_id=folder_id,
            workspace_id=workspace_id,
        )

        # Get download URL
        url = await manager.get_file_url(uploaded_file.id, expires_in=3600)

        response = FileUploadResponse(
            id=uploaded_file.id,
            name=uploaded_file.name,
            size=uploaded_file.size,
            mime_type=uploaded_file.mime_type,
            url=url,
        )

        return StandardResponse(
            data=response,
            message=f"File uploaded successfully: {uploaded_file.name}",
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@router.post("/upload/multiple", response_model=StandardResponse[List[FileUploadResponse]], status_code=201)
async def upload_multiple_files(
    files: List[UploadFile] = FastAPIFile(...),
    folder_id: Optional[UUID] = Query(None),
    workspace_id: Optional[UUID] = Query(None),
    manager: FileManager = Depends(get_file_manager),
):
    """
    Upload multiple files at once

    Example:
        curl -X POST http://localhost:8000/api/files/upload/multiple \\
            -F "files=@file1.pdf" \\
            -F "files=@file2.jpg" \\
            -F "files=@file3.docx"
    """
    uploaded_files = []

    for file in files:
        try:
            file_data = await file.read()
            file_obj = io.BytesIO(file_data)

            uploaded_file = await manager.upload_file(
                file_data=file_obj,
                filename=file.filename,
                folder_id=folder_id,
                workspace_id=workspace_id,
            )

            url = await manager.get_file_url(uploaded_file.id, expires_in=3600)

            uploaded_files.append(FileUploadResponse(
                id=uploaded_file.id,
                name=uploaded_file.name,
                size=uploaded_file.size,
                mime_type=uploaded_file.mime_type,
                url=url,
            ))

        except Exception as e:
            # Log error but continue with other files
            print(f"Failed to upload {file.filename}: {e}")

    return StandardResponse(
        data=uploaded_files,
        message=f"Uploaded {len(uploaded_files)} of {len(files)} files",
    )


# ============================================================================
# File Download Endpoints
# ============================================================================


@router.get("/{file_id}/download")
async def download_file(
    file_id: UUID,
    manager: FileManager = Depends(get_file_manager),
):
    """
    Download file (full download)

    Returns file with proper Content-Disposition header for download.

    Example:
        curl http://localhost:8000/api/files/{file_id}/download -o myfile.pdf
    """
    try:
        # Get file metadata
        file = await manager.file_repo.get_by_id(file_id)

        if not file:
            raise HTTPException(status_code=404, detail="File not found")

        # Download file content
        file_data = await manager.download_file(file_id)

        return Response(
            content=file_data,
            media_type=file.mime_type,
            headers={
                "Content-Disposition": f'attachment; filename="{file.original_name}"',
                "Content-Length": str(len(file_data)),
            },
        )

    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="File not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Download failed: {str(e)}")


@router.get("/{file_id}/stream")
async def stream_file(
    file_id: UUID,
    manager: FileManager = Depends(get_file_manager),
):
    """
    Stream file (chunked download)

    Efficient for large files - streams in chunks to reduce memory usage.
    Supports range requests for video/audio playback.

    Example:
        <video src="http://localhost:8000/api/files/{file_id}/stream" controls></video>
    """
    try:
        # Get file metadata
        file = await manager.file_repo.get_by_id(file_id)

        if not file:
            raise HTTPException(status_code=404, detail="File not found")

        # Stream file content
        async def file_stream():
            async for chunk in manager.stream_file(file_id, chunk_size=8192):
                yield chunk

        return StreamingResponse(
            file_stream(),
            media_type=file.mime_type,
            headers={
                "Content-Disposition": f'inline; filename="{file.original_name}"',
                "Accept-Ranges": "bytes",
            },
        )

    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="File not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Stream failed: {str(e)}")


@router.get("/{file_id}/url")
async def get_file_url(
    file_id: UUID,
    expires_in: int = Query(3600, description="URL expiration in seconds"),
    manager: FileManager = Depends(get_file_manager),
):
    """
    Get temporary signed URL for file access

    Useful for:
    - Sharing files with expiration
    - CDN integration
    - Client-side downloads

    Example:
        GET /api/files/{file_id}/url?expires_in=7200
    """
    try:
        url = await manager.get_file_url(file_id, expires_in=expires_in)

        return StandardResponse(
            data={"url": url, "expires_in": expires_in},
            message="Temporary URL generated",
        )

    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="File not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate URL: {str(e)}")


# ============================================================================
# File Management Endpoints
# ============================================================================


@router.get("/", response_model=PaginatedResponse[FileResponse])
async def list_files(
    folder_id: Optional[UUID] = Query(None),
    workspace_id: Optional[UUID] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    manager: FileManager = Depends(get_file_manager),
):
    """
    List files with pagination and filtering

    Example:
        GET /api/files?workspace_id=uuid&folder_id=uuid&page=1&limit=50
    """
    offset = (page - 1) * limit

    files = await manager.list_files(
        folder_id=folder_id,
        workspace_id=workspace_id,
        limit=limit,
        offset=offset,
    )

    # Count total files
    total = await manager.file_repo.count(
        filters=[
            File.folder_id == folder_id if folder_id else None,
            File.workspace_id == workspace_id if workspace_id else None,
        ]
    )

    # Convert to response models
    file_responses = [
        FileResponse(**file.to_dict())
        for file in files
    ]

    return PaginatedResponse.create(
        items=file_responses,
        total=total,
        page=page,
        limit=limit,
    )


@router.get("/{file_id}", response_model=StandardResponse[FileResponse])
async def get_file_metadata(
    file_id: UUID,
    manager: FileManager = Depends(get_file_manager),
):
    """
    Get file metadata

    Example:
        GET /api/files/{file_id}
    """
    file = await manager.file_repo.get_by_id(file_id)

    if not file:
        raise HTTPException(status_code=404, detail="File not found")

    return StandardResponse(
        data=FileResponse(**file.to_dict()),
        message="File metadata retrieved",
    )


@router.delete("/{file_id}", status_code=204)
async def delete_file(
    file_id: UUID,
    permanent: bool = Query(False, description="Permanently delete file"),
    manager: FileManager = Depends(get_file_manager),
):
    """
    Delete file (soft or hard delete)

    Soft delete (default): Marks as deleted, can be restored
    Hard delete: Permanently removes file and storage

    Example:
        DELETE /api/files/{file_id}?permanent=true
    """
    deleted = await manager.delete_file(file_id, permanent=permanent)

    if not deleted:
        raise HTTPException(status_code=404, detail="File not found")


@router.post("/search", response_model=StandardResponse[List[FileResponse]])
async def search_files(
    request: FileSearchRequest,
    manager: FileManager = Depends(get_file_manager),
):
    """
    Search files by name and filters

    Example:
        POST /api/files/search
        {
            "query": "report",
            "workspace_id": "uuid",
            "mime_type": "application/pdf",
            "limit": 20
        }
    """
    files = await manager.search_files(
        query=request.query,
        workspace_id=request.workspace_id,
        mime_type=request.mime_type,
        limit=request.limit,
    )

    file_responses = [FileResponse(**file.to_dict()) for file in files]

    return StandardResponse(
        data=file_responses,
        message=f"Found {len(files)} matching files",
    )


# ============================================================================
# Folder Management Endpoints
# ============================================================================


@router.post("/folders", response_model=StandardResponse[FolderResponse], status_code=201)
async def create_folder(
    request: FolderCreate,
    manager: FileManager = Depends(get_file_manager),
):
    """
    Create a folder

    Example:
        POST /api/files/folders
        {
            "name": "Documents",
            "parent_id": "uuid",
            "workspace_id": "uuid",
            "description": "Project documents"
        }
    """
    folder = await manager.create_folder(
        name=request.name,
        parent_id=request.parent_id,
        workspace_id=request.workspace_id,
        description=request.description,
    )

    return StandardResponse(
        data=FolderResponse.model_validate(folder),
        message=f"Folder created: {folder.name}",
    )


@router.get("/folders/{folder_id}", response_model=StandardResponse[FolderResponse])
async def get_folder(
    folder_id: UUID,
    manager: FileManager = Depends(get_file_manager),
):
    """Get folder metadata"""
    folder = await manager.folder_repo.get_by_id(folder_id)

    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")

    return StandardResponse(
        data=FolderResponse.model_validate(folder),
        message="Folder retrieved",
    )


@router.delete("/folders/{folder_id}", status_code=204)
async def delete_folder(
    folder_id: UUID,
    manager: FileManager = Depends(get_file_manager),
):
    """Delete folder (soft delete)"""
    deleted = await manager.folder_repo.delete(folder_id)

    if not deleted:
        raise HTTPException(status_code=404, detail="Folder not found")
