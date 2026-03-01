"""
File Manager - High-Level File Management API

Coordinates storage backends, database, and file operations.
"""

from uuid import UUID, uuid4
from typing import Optional, BinaryIO, List
from datetime import datetime
from pathlib import Path
import mimetypes

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_

from velvetecho.files.models import File, Folder, FileVersion
from velvetecho.files.storage import StorageBackend, LocalStorage
from velvetecho.database import Repository


class FileManager:
    """
    High-level file management API

    Handles:
    - File upload/download
    - Folder management
    - File versioning
    - File metadata
    - Access control
    """

    def __init__(
        self,
        session: AsyncSession,
        storage: StorageBackend,
        default_owner: str = "system",
    ):
        """
        Initialize file manager

        Args:
            session: Database session
            storage: Storage backend
            default_owner: Default owner ID for files
        """
        self.session = session
        self.storage = storage
        self.default_owner = default_owner
        self.file_repo = Repository(session, File)
        self.folder_repo = Repository(session, Folder)

    async def upload_file(
        self,
        file_data: BinaryIO,
        filename: str,
        folder_id: Optional[UUID] = None,
        owner_id: Optional[str] = None,
        workspace_id: Optional[UUID] = None,
        metadata: Optional[dict] = None,
        create_version: bool = False,
    ) -> File:
        """
        Upload a file

        Args:
            file_data: File binary data
            filename: Original filename
            folder_id: Parent folder ID
            owner_id: File owner ID
            workspace_id: Workspace ID
            metadata: Additional metadata
            create_version: Create new version if file exists

        Returns:
            Created File model
        """
        # Generate unique storage path
        file_id = uuid4()
        extension = Path(filename).suffix
        storage_path = self._generate_storage_path(file_id, extension)

        # Detect MIME type
        mime_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"

        # Save to storage
        await self.storage.save(
            file_data,
            storage_path,
            content_type=mime_type,
            metadata=metadata,
        )

        # Get file size
        file_data.seek(0, 2)  # Seek to end
        file_size = file_data.tell()
        file_data.seek(0)  # Reset to beginning

        # Calculate hashes
        md5_hash = await self.storage.calculate_md5(storage_path) if hasattr(self.storage, 'calculate_md5') else None
        sha256_hash = await self.storage.calculate_sha256(storage_path) if hasattr(self.storage, 'calculate_sha256') else None

        # Create file record
        file_model = File(
            id=file_id,
            name=filename,
            original_name=filename,
            mime_type=mime_type,
            size=file_size,
            extension=extension.lstrip(".") if extension else None,
            storage_backend=self.storage.__class__.__name__.lower().replace("storage", ""),
            storage_path=storage_path,
            folder_id=folder_id,
            owner_id=owner_id or self.default_owner,
            workspace_id=workspace_id,
            md5_hash=md5_hash,
            sha256_hash=sha256_hash,
            metadata=metadata,
        )

        await self.file_repo.create(file_model)

        return file_model

    async def download_file(self, file_id: UUID) -> bytes:
        """
        Download file content

        Args:
            file_id: File ID

        Returns:
            File binary data
        """
        file = await self.file_repo.get_by_id(file_id)

        if not file:
            raise FileNotFoundError(f"File not found: {file_id}")

        # Update access stats
        file.access_count += 1
        file.last_accessed_at = datetime.utcnow()
        await self.file_repo.update(file_id, {
            "access_count": file.access_count,
            "last_accessed_at": file.last_accessed_at,
        })

        # Download from storage
        return await self.storage.read(file.storage_path)

    async def stream_file(self, file_id: UUID, chunk_size: int = 8192):
        """
        Stream file content

        Args:
            file_id: File ID
            chunk_size: Chunk size in bytes

        Yields:
            File chunks
        """
        file = await self.file_repo.get_by_id(file_id)

        if not file:
            raise FileNotFoundError(f"File not found: {file_id}")

        # Update access stats
        file.access_count += 1
        file.last_accessed_at = datetime.utcnow()
        await self.file_repo.update(file_id, {
            "access_count": file.access_count,
            "last_accessed_at": file.last_accessed_at,
        })

        # Stream from storage
        async for chunk in self.storage.stream(file.storage_path, chunk_size):
            yield chunk

    async def delete_file(self, file_id: UUID, permanent: bool = False) -> bool:
        """
        Delete file (soft or hard delete)

        Args:
            file_id: File ID
            permanent: Permanently delete file and storage

        Returns:
            True if deleted
        """
        file = await self.file_repo.get_by_id(file_id)

        if not file:
            return False

        if permanent:
            # Delete from storage
            await self.storage.delete(file.storage_path)

            # Delete from database
            await self.file_repo.delete(file_id)
        else:
            # Soft delete
            await self.file_repo.delete(file_id)

        return True

    async def create_folder(
        self,
        name: str,
        parent_id: Optional[UUID] = None,
        owner_id: Optional[str] = None,
        workspace_id: Optional[UUID] = None,
        description: Optional[str] = None,
    ) -> Folder:
        """
        Create a folder

        Args:
            name: Folder name
            parent_id: Parent folder ID
            owner_id: Folder owner ID
            workspace_id: Workspace ID
            description: Folder description

        Returns:
            Created Folder model
        """
        # Build path
        if parent_id:
            parent = await self.folder_repo.get_by_id(parent_id)
            if not parent:
                raise ValueError(f"Parent folder not found: {parent_id}")
            path = f"{parent.path}/{name}"
        else:
            path = f"/{name}"

        folder = Folder(
            name=name,
            path=path,
            parent_id=parent_id,
            owner_id=owner_id or self.default_owner,
            workspace_id=workspace_id,
            description=description,
        )

        await self.folder_repo.create(folder)

        return folder

    async def list_files(
        self,
        folder_id: Optional[UUID] = None,
        workspace_id: Optional[UUID] = None,
        owner_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[File]:
        """
        List files

        Args:
            folder_id: Filter by folder
            workspace_id: Filter by workspace
            owner_id: Filter by owner
            limit: Max results
            offset: Result offset

        Returns:
            List of File models
        """
        filters = []

        if folder_id:
            filters.append(File.folder_id == folder_id)
        if workspace_id:
            filters.append(File.workspace_id == workspace_id)
        if owner_id:
            filters.append(File.owner_id == owner_id)

        return await self.file_repo.list(
            filters=filters,
            limit=limit,
            offset=offset,
        )

    async def search_files(
        self,
        query: str,
        workspace_id: Optional[UUID] = None,
        mime_type: Optional[str] = None,
        limit: int = 50,
    ) -> List[File]:
        """
        Search files by name

        Args:
            query: Search query
            workspace_id: Filter by workspace
            mime_type: Filter by MIME type
            limit: Max results

        Returns:
            List of matching files
        """
        stmt = select(File).where(
            File.name.ilike(f"%{query}%")
        )

        if workspace_id:
            stmt = stmt.where(File.workspace_id == workspace_id)

        if mime_type:
            stmt = stmt.where(File.mime_type.startswith(mime_type))

        stmt = stmt.limit(limit)

        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_file_url(
        self,
        file_id: UUID,
        expires_in: Optional[int] = 3600,
    ) -> str:
        """
        Get temporary signed URL for file

        Args:
            file_id: File ID
            expires_in: Expiration in seconds

        Returns:
            Signed URL
        """
        file = await self.file_repo.get_by_id(file_id)

        if not file:
            raise FileNotFoundError(f"File not found: {file_id}")

        return await self.storage.get_url(
            file.storage_path,
            expires_in=expires_in,
            response_headers={
                "ResponseContentDisposition": f'attachment; filename="{file.original_name}"',
                "ResponseContentType": file.mime_type,
            },
        )

    def _generate_storage_path(self, file_id: UUID, extension: str) -> str:
        """Generate unique storage path"""
        now = datetime.utcnow()
        date_path = f"{now.year}/{now.month:02d}/{now.day:02d}"
        return f"{date_path}/{file_id}{extension}"
