"""
UploadThing Python SDK.

A Python client for the UploadThing file upload service.
"""

from uploadthing_py.utapi import UTApi, HttpError, UploadError
from uploadthing_py.ut_file import UTFile
from uploadthing_py.config import UTConfig, ConfigError, parse_token, get_config_from_env
from uploadthing_py.types import (
    ACL,
    ContentDisposition,
    File,
    DeleteFiles,
    ListFiles,
    RenameFiles,
    GetUsageInfo,
    GetSignedUrl,
    UpdateACL,
    UploadFiles,
    GenerateSignedUrl,
    UploadThingRequestBody,
)
from uploadthing_py.request_handler import create_route_handler, extract_router_config
from uploadthing_py.builder import create_uploadthing

__version__ = "0.2.0"

__all__ = [
    # Main classes
    "UTApi",
    "UTFile",
    "UTConfig",
    # Builder pattern
    "create_uploadthing",
    "extract_router_config",
    "create_route_handler",
    # Errors
    "HttpError",
    "UploadError",
    "ConfigError",
    # Config functions
    "parse_token",
    "get_config_from_env",
    # Types
    "ACL",
    "ContentDisposition",
    "File",
    "DeleteFiles",
    "ListFiles",
    "RenameFiles",
    "GetUsageInfo",
    "GetSignedUrl",
    "UpdateACL",
    "UploadFiles",
    "GenerateSignedUrl",
    "UploadThingRequestBody",
]
