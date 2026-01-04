"""
UTApi - UploadThing API client for Python.

This module provides an asynchronous client for interacting with the UploadThing API,
including file uploads, management, and signed URL generation.
"""

import typing as t
import logging
import asyncio
from dataclasses import dataclass
from httpx import AsyncClient, Response

import uploadthing_py
from uploadthing_py.config import UTConfig, get_config_from_env, ConfigError
from uploadthing_py.ut_file import UTFile

from uploadthing_py.types import (
    ACL,
    ContentDisposition,
    MaybeList,
    File,
    ListFiles,
    DeleteFiles,
    RenameFiles,
    GetUsageInfo,
    GetSignedUrl,
    UpdateACL,
    UploadFiles,
    GenerateSignedUrl,
)
from uploadthing_py.utils import json_stringify, del_none, generate_key, generate_signed_url


class HttpError(Exception):
    """HTTP error from UploadThing API."""

    def __init__(self, response: Response):
        self.status_code = response.status_code
        self.message = response.text

    def __str__(self):
        return f"HTTP Error: {self.status_code} {self.message}"


class UploadError(Exception):
    """Error during file upload."""

    def __init__(self, code: str, message: str, data: t.Any = None):
        self.code = code
        self.message = message
        self.data = data

    def __str__(self):
        return f"UploadError({self.code}): {self.message}"


class UTApi:
    """An asynchronous client for the UploadThing API.

    Args:
        token: The UPLOADTHING_TOKEN (Base64-encoded JSON with apiKey and appId).
               If not provided, reads from UPLOADTHING_TOKEN environment variable.
        key_type: Set the default key type for file operations.
        api_url: Override the API server URL.
        ingest_url: Override the ingest server URL.
        ufs_host: Override the UFS (file storage) host.
    """

    def __init__(
        self,
        token: str | None = None,
        key_type: t.Literal["file_key", "custom_id"] = "file_key",
        api_url: str | None = None,
        ingest_url: str | None = None,
        ufs_host: str | None = None,
    ):
        # Parse token and get configuration
        self._config = get_config_from_env(
            token=token,
            api_url=api_url,
            ingest_url=ingest_url,
            ufs_host=ufs_host,
        )

        self._client = AsyncClient(
            base_url=self._config.api_url,
            headers={
                "x-uploadthing-api-key": self._config.api_key,
                "x-uploadthing-be-adapter": f"uploadthing_py@{uploadthing_py.__version__}",
                "x-uploadthing-version": "7.7.4",
            },
        )
        self._default_key_type = key_type
        self._logger = logging.getLogger("uploadthing_py")

    @property
    def app_id(self) -> str:
        """Get the app ID from the token."""
        return self._config.app_id

    async def _request_ut_api(self, path: str, payload: t.Dict | None = None) -> t.Dict:
        """Make a request to the UploadThing API."""
        stringified = json_stringify(del_none(payload or {}))
        self._logger.debug(f"Requesting UploadThing API with: {path} {stringified}")
        response = await self._client.post(
            path,
            content=stringified,
            headers={"Content-Type": "application/json"},
        )
        self._logger.debug(
            f"UploadThing API returned with: {response.status_code} {response.text}"
        )

        if response.status_code != 200:
            raise HttpError(response)

        return response.json()

    async def _upload_single_file(
        self,
        file: UTFile,
        content_disposition: ContentDisposition,
        acl: ACL | None,
    ) -> UploadFiles.UploadResult:
        """Upload a single file to UploadThing."""
        try:
            # Generate file key using SQIDs (matching TypeScript SDK)
            key = generate_key(
                file_name=file.name,
                file_size=file.size,
                file_type=file.content_type,
                app_id=self._config.app_id,
                last_modified=file.last_modified,
            )

            # Build the presigned URL with metadata
            base_url = f"{self._config.ingest_url}/{key}"
            presigned_url = generate_signed_url(
                base_url=base_url,
                api_key=self._config.api_key,
                data={
                    "x-ut-identifier": self._config.app_id,
                    "x-ut-file-name": file.name,
                    "x-ut-file-size": file.size,
                    "x-ut-file-type": file.content_type,
                    "x-ut-custom-id": file.custom_id,
                    "x-ut-content-disposition": content_disposition,
                    "x-ut-acl": acl,
                },
                ttl_seconds=300,  # 5 minutes
            )

            self._logger.debug(f"Uploading file {file.name} to {presigned_url[:100]}...")

            # Upload the file via HTTP PUT with FormData (matching TypeScript SDK)
            async with AsyncClient() as upload_client:
                files = {"file": (file.name, file.content, file.content_type)}
                response = await upload_client.put(
                    presigned_url,
                    files=files,
                    headers={
                        "Range": "bytes=0-",
                        "x-uploadthing-version": "6.10.0",
                    },
                    timeout=300.0,  # 5 minute timeout for large files
                )

                if response.status_code != 200:
                    self._logger.error(f"Upload failed: {response.status_code} {response.text}")
                    return UploadFiles.UploadResult(
                        error=UploadFiles.UploadError(
                            code="UPLOAD_FAILED",
                            message=f"Upload failed with status {response.status_code}",
                            data=response.text,
                        )
                    )

                # Parse response
                result = response.json()

            # Build file URLs
            ufs_url = f"https://{self._config.app_id}.{self._config.ufs_host}/f/{key}"
            app_url = ufs_url  # Same for now

            return UploadFiles.UploadResult(
                data=UploadFiles.UploadedFile(
                    key=key,
                    url=result.get("url", ufs_url),
                    app_url=result.get("appUrl", app_url),
                    ufs_url=result.get("ufsUrl", ufs_url),
                    name=file.name,
                    size=file.size,
                    type=file.content_type,
                    custom_id=file.custom_id,
                    file_hash=result.get("fileHash", ""),
                    last_modified=file.last_modified,
                )
            )

        except Exception as e:
            self._logger.exception(f"Error uploading file {file.name}")
            return UploadFiles.UploadResult(
                error=UploadFiles.UploadError(
                    code="UPLOAD_FAILED",
                    message=str(e),
                )
            )

    async def upload_files(
        self,
        files: MaybeList[UTFile],
        options: UploadFiles.UploadFilesOptions | None = None,
    ) -> MaybeList[UploadFiles.UploadResult]:
        """
        Upload files to UploadThing storage.

        Args:
            files: A single UTFile or list of UTFile objects to upload
            options: Upload options (content_disposition, acl, concurrency)

        Returns:
            A single UploadResult or list of UploadResults depending on input

        Example:
            # Single file
            result = await utapi.upload_files(UTFile.from_path("image.png"))
            if result.is_success:
                print(f"Uploaded: {result.data.url}")

            # Multiple files
            results = await utapi.upload_files([
                UTFile.from_path("image1.png"),
                UTFile.from_path("image2.png"),
            ], options=UploadFiles.UploadFilesOptions(concurrency=2))
        """
        opts = options or UploadFiles.UploadFilesOptions()
        content_disposition = opts.content_disposition
        acl = opts.acl
        concurrency = max(1, min(25, opts.concurrency))  # Clamp between 1 and 25

        # Normalize to list
        is_single = not isinstance(files, list)
        file_list = [files] if is_single else files

        # Create upload tasks
        semaphore = asyncio.Semaphore(concurrency)

        async def upload_with_semaphore(file: UTFile) -> UploadFiles.UploadResult:
            async with semaphore:
                return await self._upload_single_file(file, content_disposition, acl)

        # Run uploads concurrently
        results = await asyncio.gather(
            *[upload_with_semaphore(f) for f in file_list]
        )

        self._logger.debug(f"Finished uploading {len(results)} files")

        return results[0] if is_single else list(results)

    async def upload_files_from_url(
        self,
        urls: MaybeList[str],
        options: UploadFiles.UploadFilesOptions | None = None,
    ) -> MaybeList[UploadFiles.UploadResult]:
        """
        Download files from URLs and upload them to UploadThing.

        Args:
            urls: A single URL or list of URLs to download and upload
            options: Upload options (content_disposition, acl, concurrency)

        Returns:
            A single UploadResult or list of UploadResults depending on input

        Example:
            result = await utapi.upload_files_from_url(
                "https://example.com/image.png"
            )
        """
        opts = options or UploadFiles.UploadFilesOptions()
        concurrency = max(1, min(25, opts.concurrency))

        is_single = not isinstance(urls, list)
        url_list = [urls] if is_single else urls

        semaphore = asyncio.Semaphore(concurrency)

        async def download_and_upload(url: str) -> UploadFiles.UploadResult:
            async with semaphore:
                try:
                    # Download the file
                    async with AsyncClient() as client:
                        response = await client.get(url, follow_redirects=True)

                        if response.status_code != 200:
                            return UploadFiles.UploadResult(
                                error=UploadFiles.UploadError(
                                    code="DOWNLOAD_FAILED",
                                    message=f"Failed to download from {url}: {response.status_code}",
                                )
                            )

                        # Extract filename from URL
                        from urllib.parse import urlparse
                        parsed = urlparse(url)
                        filename = parsed.path.split("/")[-1] or "unknown"

                        # Create UTFile from downloaded content
                        file = UTFile(
                            content=response.content,
                            name=filename,
                            content_type=response.headers.get("content-type"),
                        )

                    # Upload the file
                    return await self._upload_single_file(
                        file,
                        opts.content_disposition,
                        opts.acl,
                    )

                except Exception as e:
                    return UploadFiles.UploadResult(
                        error=UploadFiles.UploadError(
                            code="DOWNLOAD_FAILED",
                            message=f"Error downloading {url}: {str(e)}",
                        )
                    )

        results = await asyncio.gather(*[download_and_upload(url) for url in url_list])

        return results[0] if is_single else list(results)

    async def delete_files(
        self,
        keys: MaybeList[str],
        options: t.Optional[DeleteFiles.DeleteFileOptions] = None,
    ):
        """Delete files from UploadThing storage."""
        if not isinstance(keys, list):
            keys = [keys]

        key_type = options["key_type"] if options else self._default_key_type
        payload = {"fileKeys": keys} if key_type == "file_key" else {"customIds": keys}

        api_response = await self._request_ut_api("/v6/deleteFiles", payload)
        response = DeleteFiles.DeleteFileResponse.from_api_response(api_response)

        return response

    async def list_files(self, options: t.Optional[ListFiles.ListFilesOptions] = None):
        """List files in your UploadThing app."""
        api_response = await self._request_ut_api("/v6/listFiles", options)
        response = ListFiles.ListFilesResponse(**api_response)

        files = [File.from_api_response(file) for file in response.files]

        return files

    async def rename_files(self, updates: RenameFiles.RenameFileOptions):
        """Rename files in UploadThing storage."""
        if not isinstance(updates, list):
            updates = [updates]
        self._logger.debug(f"Rename files: {updates}")

        updates = [
            (
                {
                    "customId": update["custom_id"],
                    "newName": update["new_name"],
                }
                if "custom_id" in update
                else {
                    "fileKey": update["key"],
                    "newName": update["new_name"],
                }
            )
            for update in updates
        ]

        api_response = await self._request_ut_api(
            "/v6/renameFiles", {"updates": updates}
        )
        response = RenameFiles.RenameFileResponse.from_api_response(api_response)

        return response

    async def get_usage_info(self):
        """Get storage usage information for your app."""
        api_response = await self._request_ut_api("/v6/getUsageInfo")
        response = GetUsageInfo.GetUsageInfoResponse.from_api_response(api_response)

        return response

    def generate_signed_url(
        self,
        key: str,
        options: GenerateSignedUrl.GenerateSignedUrlOptions | None = None,
    ) -> GenerateSignedUrl.GenerateSignedUrlResponse:
        """
        Generate a presigned URL for a private file (local signing, no API call).

        This is the recommended way to generate signed URLs as it doesn't
        require a network request.

        Args:
            key: The file key
            options: Options including expires_in (seconds, default 300)

        Returns:
            GenerateSignedUrlResponse with the signed ufs_url

        Example:
            response = utapi.generate_signed_url("file-key")
            print(response.ufs_url)  # Use this URL to access the file
        """
        expires_in = 300  # Default: 5 minutes
        if options and options.expires_in:
            expires_in = options.expires_in

        # Validate expiration
        if expires_in > 86400 * 7:
            raise ValueError("expires_in must be less than 7 days (604800 seconds)")

        # Build the file URL
        ufs_host = self._config.ufs_host
        proto = "http" if "local" in ufs_host else "https"
        url_base = f"{proto}://{self._config.app_id}.{ufs_host}/f/{key}"

        # Generate signed URL
        signed_url = generate_signed_url(
            base_url=url_base,
            api_key=self._config.api_key,
            ttl_seconds=expires_in,
        )

        return GenerateSignedUrl.GenerateSignedUrlResponse(ufs_url=signed_url)

    async def get_signed_url(
        self, key: str, options: t.Optional[GetSignedUrl.GetSignedUrlOptions] = None
    ):
        """
        Request a presigned URL for a private file via API call.

        Note: Consider using generate_signed_url() instead as it's faster
        (no network request required).
        """
        expires_in = options["expires_in"] if options else None
        key_type = options["key_type"] if options else self._default_key_type
        payload = (
            {"fileKey": key, "expiresIn": expires_in}
            if key_type == "file_key"
            else {"customId": key, "expiresIn": expires_in}
        )

        api_response = await self._request_ut_api("/v6/requestFileAccess", payload)
        response = GetSignedUrl.GetSignedUrlResponse(**api_response)

        return response

    async def update_acl(
        self,
        keys: MaybeList[str],
        acl: ACL,
        options: t.Optional[UpdateACL.UpdateACLOptions] = None,
    ):
        """Update the ACL (access control) of files."""
        if not isinstance(keys, list):
            keys = [keys]
        key_type = options["key_type"] if options else self._default_key_type
        updates = [
            (
                {"fileKey": key, "acl": acl}
                if key_type == "file_key"
                else {"customId": key, "acl": acl}
            )
            for key in keys
        ]
        payload = {"updates": updates}

        api_response = await self._request_ut_api("/v6/updateACL", payload)
        response = UpdateACL.UpdateACLResponse.from_api_response(api_response)

        return response

    async def close(self):
        """Close the HTTP client."""
        await self._client.aclose()
        

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
