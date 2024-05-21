from typing import Any, Literal, Union, TypedDict
from dataclasses import dataclass
from pydantic import BaseModel

type MaybeList[T] = Union[list[T], T]

type ACL = Literal["public-read", "private"]


#
# UTApi Types
#


@dataclass
class File:
    id: str
    custom_id: str
    key: str
    name: str
    status: str

    @classmethod
    def from_api_response(cls, api_response: dict) -> "File":
        return File(
            id=api_response["id"],
            custom_id=api_response["customId"],
            key=api_response["key"],
            name=api_response["name"],
            status=api_response["status"],
        )


class KeyTypeOptions(TypedDict):
    key_type: Literal["custom_id", "file_key"]


class DeleteFiles:
    @dataclass
    class DeleteFileOptions(KeyTypeOptions):
        pass

    @dataclass
    class DeleteFileResponse:
        deleted_count: int
        success: bool

        @classmethod
        def from_api_response(
            cls, api_response: dict
        ) -> "DeleteFiles.DeleteFileResponse":
            return DeleteFiles.DeleteFileResponse(
                deleted_count=api_response["deletedCount"],
                success=api_response["success"],
            )


class ListFiles:
    @dataclass
    class ListFilesOptions:
        limit: int | None = None
        offset: int | None = None

    @dataclass
    class ListFilesResponse:
        class RawFile(TypedDict):
            id: str
            customId: str
            key: str
            name: str
            status: str

        hasMore: bool
        files: list[RawFile]


class RenameFiles:
    class KeyRename(TypedDict):
        key: str
        new_name: str

    class CustomIdRename(TypedDict):
        custom_id: str
        new_name: str

    type RenameFileOptions = MaybeList[Union[KeyRename, CustomIdRename]]

    @dataclass
    class RenameFileResponse:
        success: bool


class GetUsageInfo:
    @dataclass
    class GetUsageInfoOptions:
        pass

    @dataclass
    class GetUsageInfoResponse:
        total_bytes: int
        app_total_bytes: int
        files_uploaded: int
        limit_bytes: int

        @classmethod
        def from_api_response(
            cls, api_response: dict
        ) -> "GetUsageInfo.GetUsageInfoResponse":
            return GetUsageInfo.GetUsageInfoResponse(
                total_bytes=api_response["totalBytes"],
                app_total_bytes=api_response["appTotalBytes"],
                files_uploaded=api_response["filesUploaded"],
                limit_bytes=api_response["limitBytes"],
            )


class GetSignedUrl:
    class GetSignedUrlOptions(KeyTypeOptions):
        expires_in: int | None = None

    @dataclass
    class GetSignedUrlResponse:
        url: str


class UpdateACL:
    class UpdateACLOptions(KeyTypeOptions):
        acl: ACL

    @dataclass
    class UpdateACLResponse:
        success: bool


#
# Handler Types
#


class FileUploadData(BaseModel):
    name: str
    size: int
    type: str


class UploadRequest(BaseModel):
    files: list[FileUploadData]


class UploadedFileData(BaseModel):
    name: str
    size: int
    type: str
    customId: str | None = None
    key: str
    url: str


class CallbackRequest(BaseModel):
    metadata: dict[str, Any]
    status: str
    file: UploadedFileData


class ETag(BaseModel):
    tag: str
    partNumber: int


class CompleteMPURequest(BaseModel):
    etags: list[ETag]
    fileKey: str
    uploadId: str


class FailureRequest(BaseModel):
    fileKey: str
    uploadId: str | None = None
    fileName: str
    storageProviderError: str | None = None


UploadThingRequestBody = Union[
    UploadRequest, CallbackRequest, CompleteMPURequest, FailureRequest
]
