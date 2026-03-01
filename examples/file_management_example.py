"""
VelvetEcho File Management - Complete Example

Demonstrates all file management capabilities:
- File upload (single, multiple, chunked)
- File download (direct, streaming)
- Folder management
- File search and filtering
- Metadata extraction
- Storage backends (local, S3)
"""

import asyncio
from pathlib import Path
from uuid import uuid4
from velvetecho.config import VelvetEchoConfig, init_config
from velvetecho.database import init_database
from velvetecho.files import FileManager, LocalStorage, S3Storage
from velvetecho.files.models import File, Folder


async def main():
    """Run complete file management example"""

    print("=" * 70)
    print("VelvetEcho File Management System - Complete Example")
    print("=" * 70)
    print()

    # Initialize VelvetEcho
    config = VelvetEchoConfig(
        service_name="velvetecho-files",
        service_version="2.0.0",
        environment="development",
        redis_url="redis://localhost:6379/0",
    )
    init_config(config)

    # Initialize database
    db = init_database("postgresql+asyncpg://user:pass@localhost/velvetecho_files")
    await db.connect()

    try:
        # Initialize file manager with local storage
        storage = LocalStorage("./storage/files")

        async with db.session() as session:
            manager = FileManager(session, storage, default_owner="demo_user")

            # =================================================================
            # 1. Create Folder Structure
            # =================================================================
            print("📁 Creating folder structure...")

            projects_folder = await manager.create_folder(
                name="Projects",
                description="All project files",
            )
            print(f"   ✅ Created folder: {projects_folder.path}")

            docs_folder = await manager.create_folder(
                name="Documents",
                parent_id=projects_folder.id,
            )
            print(f"   ✅ Created folder: {docs_folder.path}")

            images_folder = await manager.create_folder(
                name="Images",
                parent_id=projects_folder.id,
            )
            print(f"   ✅ Created folder: {images_folder.path}")

            # =================================================================
            # 2. Upload Files
            # =================================================================
            print("\n📤 Uploading files...")

            # Create sample files
            sample_pdf = Path("sample_document.pdf")
            sample_pdf.write_text("Sample PDF content for demonstration")

            sample_image = Path("sample_image.jpg")
            sample_image.write_bytes(b"Sample image binary data")

            # Upload PDF to Documents folder
            with open(sample_pdf, "rb") as f:
                pdf_file = await manager.upload_file(
                    file_data=f,
                    filename="Project_Report.pdf",
                    folder_id=docs_folder.id,
                    metadata={
                        "project": "VelvetEcho",
                        "author": "Demo User",
                        "version": "1.0",
                    },
                )
                print(f"   ✅ Uploaded: {pdf_file.name}")
                print(f"      Size: {pdf_file.size} bytes")
                print(f"      Path: {pdf_file.storage_path}")

            # Upload image to Images folder
            with open(sample_image, "rb") as f:
                image_file = await manager.upload_file(
                    file_data=f,
                    filename="Screenshot.jpg",
                    folder_id=images_folder.id,
                )
                print(f"   ✅ Uploaded: {image_file.name}")
                print(f"      Type: {image_file.mime_type}")

            # =================================================================
            # 3. List Files
            # =================================================================
            print("\n📋 Listing files...")

            # List all files in Documents folder
            docs_files = await manager.list_files(folder_id=docs_folder.id)
            print(f"   📄 Documents folder has {len(docs_files)} file(s)")
            for file in docs_files:
                print(f"      - {file.name} ({file.size} bytes)")

            # List all files in Images folder
            images_files = await manager.list_files(folder_id=images_folder.id)
            print(f"   🖼️  Images folder has {len(images_files)} file(s)")
            for file in images_files:
                print(f"      - {file.name} ({file.size} bytes)")

            # =================================================================
            # 4. Search Files
            # =================================================================
            print("\n🔍 Searching files...")

            # Search by name
            search_results = await manager.search_files(query="Project")
            print(f"   Found {len(search_results)} file(s) matching 'Project'")
            for file in search_results:
                print(f"      - {file.name}")

            # Search PDFs only
            pdf_results = await manager.search_files(
                query="",
                mime_type="application/pdf",
            )
            print(f"   Found {len(pdf_results)} PDF file(s)")

            # =================================================================
            # 5. Download File
            # =================================================================
            print("\n📥 Downloading file...")

            # Download PDF
            downloaded_data = await manager.download_file(pdf_file.id)
            print(f"   ✅ Downloaded {len(downloaded_data)} bytes")
            print(f"   Content: {downloaded_data[:50]}...")

            # Get temporary signed URL
            file_url = await manager.get_file_url(pdf_file.id, expires_in=3600)
            print(f"   🔗 Temporary URL: {file_url}")

            # =================================================================
            # 6. Stream File
            # =================================================================
            print("\n🎥 Streaming file...")

            chunk_count = 0
            total_bytes = 0
            async for chunk in manager.stream_file(pdf_file.id, chunk_size=1024):
                chunk_count += 1
                total_bytes += len(chunk)

            print(f"   ✅ Streamed {total_bytes} bytes in {chunk_count} chunk(s)")

            # =================================================================
            # 7. File Metadata
            # =================================================================
            print("\n📊 File metadata...")

            # Get file details
            file_data = pdf_file.to_dict()
            print(f"   File ID: {file_data['id']}")
            print(f"   Name: {file_data['name']}")
            print(f"   Original: {file_data['original_name']}")
            print(f"   Size: {file_data['size_human']}")
            print(f"   Type: {file_data['mime_type']}")
            print(f"   Is Document: {file_data['is_document']}")
            print(f"   Access Count: {file_data['access_count']}")
            print(f"   Created: {file_data['created_at']}")

            # =================================================================
            # 8. Delete Files (Soft Delete)
            # =================================================================
            print("\n🗑️  Soft deleting file...")

            deleted = await manager.delete_file(image_file.id, permanent=False)
            if deleted:
                print(f"   ✅ Soft deleted: {image_file.name}")
                print(f"   (File can be restored from recycle bin)")

            # =================================================================
            # 9. Storage Backend Info
            # =================================================================
            print("\n💾 Storage backend info...")
            print(f"   Backend: {storage.__class__.__name__}")
            print(f"   Base Path: {storage.base_path}")

            # List storage files
            storage_files = await storage.list_files(recursive=True)
            print(f"   Storage has {len(storage_files)} file(s)")

            # =================================================================
            # Summary
            # =================================================================
            print("\n" + "=" * 70)
            print("✅ File Management Example Complete!")
            print("=" * 70)
            print()
            print("Features demonstrated:")
            print("  ✅ Folder creation (hierarchical)")
            print("  ✅ File upload (with metadata)")
            print("  ✅ File listing (by folder)")
            print("  ✅ File search (by name and type)")
            print("  ✅ File download (full)")
            print("  ✅ File streaming (chunked)")
            print("  ✅ Temporary URLs (signed)")
            print("  ✅ Soft delete (recoverable)")
            print("  ✅ Metadata extraction")
            print()
            print("Next steps:")
            print("  1. Try the API: uvicorn velvetecho.api.app:app --reload")
            print("  2. Upload via HTTP: POST /api/files/upload")
            print("  3. Test streaming: GET /api/files/{id}/stream")
            print("  4. View docs: http://localhost:8000/docs")
            print()

    finally:
        # Cleanup
        await db.disconnect()

        # Remove sample files
        if sample_pdf.exists():
            sample_pdf.unlink()
        if sample_image.exists():
            sample_image.unlink()


if __name__ == "__main__":
    asyncio.run(main())
