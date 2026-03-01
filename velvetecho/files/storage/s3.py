"""
S3-Compatible Storage Backend

Works with AWS S3, MinIO, DigitalOcean Spaces, etc.
"""

import boto3
from botocore.exceptions import ClientError
from botocore.config import Config
from typing import BinaryIO, Optional, AsyncIterator
from datetime import datetime, timedelta

from velvetecho.files.storage.base import StorageBackend


class S3Storage(StorageBackend):
    """
    S3-compatible storage backend

    Supports:
    - AWS S3
    - MinIO
    - DigitalOcean Spaces
    - Cloudflare R2
    - Any S3-compatible storage
    """

    def __init__(
        self,
        bucket: str,
        access_key: str,
        secret_key: str,
        endpoint_url: Optional[str] = None,
        region: str = "us-east-1",
        use_ssl: bool = True,
    ):
        """
        Initialize S3 storage

        Args:
            bucket: S3 bucket name
            access_key: AWS access key ID
            secret_key: AWS secret access key
            endpoint_url: Custom endpoint (for MinIO, etc.)
            region: AWS region
            use_ssl: Use HTTPS
        """
        self.bucket = bucket

        # Initialize S3 client
        self.client = boto3.client(
            "s3",
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            endpoint_url=endpoint_url,
            region_name=region,
            config=Config(signature_version="s3v4"),
            use_ssl=use_ssl,
        )

    async def save(
        self,
        file_data: BinaryIO,
        path: str,
        content_type: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> str:
        """Upload file to S3"""
        extra_args = {}

        if content_type:
            extra_args["ContentType"] = content_type

        if metadata:
            extra_args["Metadata"] = metadata

        try:
            self.client.upload_fileobj(
                file_data,
                self.bucket,
                path,
                ExtraArgs=extra_args,
            )
            return path
        except ClientError as e:
            raise Exception(f"Failed to upload to S3: {e}")

    async def read(self, path: str) -> bytes:
        """Download file from S3"""
        try:
            response = self.client.get_object(Bucket=self.bucket, Key=path)
            return response["Body"].read()
        except ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchKey":
                raise FileNotFoundError(f"File not found: {path}")
            raise Exception(f"Failed to read from S3: {e}")

    async def stream(self, path: str, chunk_size: int = 8192) -> AsyncIterator[bytes]:
        """Stream file from S3"""
        try:
            response = self.client.get_object(Bucket=self.bucket, Key=path)

            for chunk in response["Body"].iter_chunks(chunk_size=chunk_size):
                yield chunk
        except ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchKey":
                raise FileNotFoundError(f"File not found: {path}")
            raise Exception(f"Failed to stream from S3: {e}")

    async def delete(self, path: str) -> bool:
        """Delete file from S3"""
        try:
            self.client.delete_object(Bucket=self.bucket, Key=path)
            return True
        except ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchKey":
                return False
            raise Exception(f"Failed to delete from S3: {e}")

    async def exists(self, path: str) -> bool:
        """Check if file exists in S3"""
        try:
            self.client.head_object(Bucket=self.bucket, Key=path)
            return True
        except ClientError as e:
            if e.response["Error"]["Code"] == "404":
                return False
            raise Exception(f"Failed to check existence in S3: {e}")

    async def get_size(self, path: str) -> int:
        """Get file size from S3"""
        try:
            response = self.client.head_object(Bucket=self.bucket, Key=path)
            return response["ContentLength"]
        except ClientError as e:
            if e.response["Error"]["Code"] == "404":
                raise FileNotFoundError(f"File not found: {path}")
            raise Exception(f"Failed to get size from S3: {e}")

    async def get_url(
        self,
        path: str,
        expires_in: Optional[int] = 3600,
        response_headers: Optional[dict] = None,
    ) -> str:
        """
        Generate presigned URL for S3 file

        Args:
            path: S3 key
            expires_in: Expiration in seconds (default 1 hour)
            response_headers: Headers to include in response

        Returns:
            Presigned URL
        """
        params = {"Bucket": self.bucket, "Key": path}

        if response_headers:
            params.update(response_headers)

        try:
            url = self.client.generate_presigned_url(
                "get_object",
                Params=params,
                ExpiresIn=expires_in or 3600,
            )
            return url
        except ClientError as e:
            raise Exception(f"Failed to generate presigned URL: {e}")

    async def copy(self, source_path: str, dest_path: str) -> bool:
        """Copy file within S3"""
        try:
            self.client.copy_object(
                Bucket=self.bucket,
                CopySource={"Bucket": self.bucket, "Key": source_path},
                Key=dest_path,
            )
            return True
        except ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchKey":
                raise FileNotFoundError(f"Source file not found: {source_path}")
            raise Exception(f"Failed to copy in S3: {e}")

    async def move(self, source_path: str, dest_path: str) -> bool:
        """Move file within S3 (copy + delete)"""
        await self.copy(source_path, dest_path)
        await self.delete(source_path)
        return True

    async def list_files(
        self,
        prefix: Optional[str] = None,
        recursive: bool = False,
    ) -> list[dict]:
        """List files in S3 bucket"""
        params = {"Bucket": self.bucket}

        if prefix:
            params["Prefix"] = prefix

        if not recursive:
            params["Delimiter"] = "/"

        try:
            files = []
            paginator = self.client.get_paginator("list_objects_v2")

            for page in paginator.paginate(**params):
                for obj in page.get("Contents", []):
                    files.append({
                        "path": obj["Key"],
                        "size": obj["Size"],
                        "modified": obj["LastModified"].isoformat(),
                        "etag": obj["ETag"].strip('"'),
                    })

            return files
        except ClientError as e:
            raise Exception(f"Failed to list files in S3: {e}")

    async def set_public(self, path: str, is_public: bool = True) -> bool:
        """Set file ACL (public/private)"""
        acl = "public-read" if is_public else "private"

        try:
            self.client.put_object_acl(
                Bucket=self.bucket,
                Key=path,
                ACL=acl,
            )
            return True
        except ClientError as e:
            raise Exception(f"Failed to set ACL: {e}")
