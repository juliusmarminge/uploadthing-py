import typing as t, logging
from httpx import AsyncClient, Response

import uploadthing_py
from uploadthing_py.types import (
    ACL,
    MaybeList,
    File,
    ListFiles,
    DeleteFiles,
    RenameFile,
    GetUsageInfo,
    GetSignedUrl,
    UpdateACL,
)
from uploadthing_py.utils import json_stringify, del_none


class HttpError(Exception):
    def __init__(self, response: Response):
        self.status_code = response.status_code
        self.message = response.text

    def __str__(self):
        return f"HTTP Error: {self.status_code} {self.message}"


class UTApi:
    """An asynchronous client for the UploadThing API.

    Args:
        api_key: The root api key to use for requests.
        key_type: Set the default key type for file operations.
        base_url: The base URL for the UploadThing API.
    """

    def __init__(
        self,
        api_key: str,
        key_type: t.Literal["file_key", "custom_id"] = "file_key",
        base_url: str = "https://api.uploadthing.com",
    ):
        self._api_key = api_key
        self._client = AsyncClient(
            base_url=base_url,
            headers={
                "x-uploadthing-api-key": self._api_key,
                "x-uploadthing-be-adapter": f"uploadthing_py@{uploadthing_py.__version__}",
                "x-uploadthing-version": "6.10.0",
            },
        )
        self._baseUrl = base_url
        self._default_key_type = key_type
        self._logger = logging.getLogger("uploadthing_py")

    async def _request_ut_api(self, path: str, payload: t.Dict = None) -> t.Dict:
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

    async def upload_files(
        self, files: MaybeList[t.Any], options: t.Optional[t.Any] = None
    ):
        raise NotImplementedError

    async def delete_files(
        self,
        keys: MaybeList[str],
        options: t.Optional[DeleteFiles.DeleteFileOptions] = None,
    ):
        if not isinstance(keys, t.List):
            keys = [keys]

        key_type = options["key_type"] if options else self._default_key_type
        payload = {"fileKeys": keys} if key_type == "file_key" else {"customIds": keys}

        api_response = await self._request_ut_api("/v6/deleteFiles", payload)
        response = DeleteFiles.DeleteFileResponse(**api_response)

        return response

    async def list_files(self, options: t.Optional[ListFiles.ListFilesOptions] = None):
        api_response = await self._request_ut_api("/v6/listFiles", options)
        response = ListFiles.ListFilesResponse(**api_response)

        files = [File.from_api_response(file) for file in response.files]

        return files

    async def rename_files(self, updates: RenameFile.RenameFileOptions):
        if not isinstance(updates, t.List):
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
        response = RenameFile.RenameFileResponse(**api_response)

        return response

    async def get_usage_info(self):
        api_response = await self._request_ut_api("/v6/getUsageInfo")
        response = GetUsageInfo.GetUsageInfoResponse.from_api_response(api_response)

        return response

    async def get_signed_url(
        self, key: str, options: t.Optional[GetSignedUrl.GetSignedUrlOptions] = None
    ):
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
        if not isinstance(keys, t.List):
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
        response = UpdateACL.UpdateACLResponse(**api_response)

        return response
