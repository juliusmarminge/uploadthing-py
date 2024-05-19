import typing as t
from dataclasses import dataclass


type MaybeList[T] = t.Union[t.List[T], T]

type ACL = t.Literal["public-read", "private"]


@dataclass
class File:
    id: str
    custom_id: str
    key: str
    name: str
    status: str

    @classmethod
    def from_api_response(cls, api_response: t.Dict) -> "File":
        return File(
            id=api_response["id"],
            custom_id=api_response["customId"],
            key=api_response["key"],
            name=api_response["name"],
            status=api_response["status"],
        )


class KeyTypeOptions(t.TypedDict):
    key_type: t.Literal["custom_id", "file_key"]


class DeleteFiles:
    @dataclass
    class DeleteFileOptions(KeyTypeOptions):
        pass

    @dataclass
    class DeleteFileResponse:
        success: bool


class ListFiles:
    @dataclass
    class ListFilesOptions:
        limit: t.Optional[int] = None
        offset: t.Optional[int] = None

    @dataclass
    class ListFilesResponse:
        class RawFile(t.TypedDict):
            id: str
            customId: str
            key: str
            name: str
            status: str

        hasMore: bool
        files: t.List[RawFile]


class RenameFile:
    class KeyRename(t.TypedDict):
        key: str
        new_name: str

    class CustomIdRename(t.TypedDict):
        custom_id: str
        new_name: str

    type RenameFileOptions = MaybeList[t.Union[KeyRename, CustomIdRename]]

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
            cls, api_response: t.Dict
        ) -> "GetUsageInfo.GetUsageInfoResponse":
            return GetUsageInfo.GetUsageInfoResponse(
                total_bytes=api_response["totalBytes"],
                app_total_bytes=api_response["appTotalBytes"],
                files_uploaded=api_response["filesUploaded"],
                limit_bytes=api_response["limitBytes"],
            )


class GetSignedUrl:
    class GetSignedUrlOptions(KeyTypeOptions):
        expires_in: t.Optional[int] = None

    class GetSignedUrlResponse:
        url: str


class UpdateACL:
    class UpdateACLOptions(KeyTypeOptions):
        acl: ACL

    @dataclass
    class UpdateACLResponse:
        success: bool
