"""
UTFile class for file uploads.

Provides a simple wrapper around file content with metadata.
"""

from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path
from typing import BinaryIO
import time

from uploadthing_py.mime import lookup_or_default


@dataclass
class UTFile:
    """
    File wrapper for UploadThing uploads.

    Similar to the TypeScript UTFile class, this provides a consistent
    interface for file uploads with name, content type, and optional customId.
    """

    content: bytes
    name: str
    content_type: str
    size: int
    custom_id: str | None = None
    last_modified: int = field(default_factory=lambda: int(time.time() * 1000))

    def __init__(
        self,
        content: bytes | BinaryIO | BytesIO,
        name: str,
        content_type: str | None = None,
        custom_id: str | None = None,
        last_modified: int | None = None,
    ):
        """
        Create a new UTFile.

        Args:
            content: The file content as bytes or a file-like object
            name: The filename
            content_type: Optional MIME type. If not provided, will be detected from filename.
            custom_id: Optional custom identifier for the file
            last_modified: Optional timestamp in milliseconds. Defaults to current time.
        """
        # Handle file-like objects
        if hasattr(content, "read"):
            self.content = content.read()
        else:
            self.content = content

        self.name = name
        self.content_type = content_type or lookup_or_default(name)
        self.size = len(self.content)
        self.custom_id = custom_id
        self.last_modified = last_modified or int(time.time() * 1000)

    @classmethod
    def from_path(
        cls,
        path: str | Path,
        name: str | None = None,
        content_type: str | None = None,
        custom_id: str | None = None,
    ) -> "UTFile":
        """
        Create a UTFile from a file path.

        Args:
            path: Path to the file
            name: Optional filename override. Defaults to the file's basename.
            content_type: Optional MIME type override.
            custom_id: Optional custom identifier.

        Returns:
            A new UTFile instance
        """
        path = Path(path)
        with open(path, "rb") as f:
            content = f.read()

        return cls(
            content=content,
            name=name or path.name,
            content_type=content_type,
            custom_id=custom_id,
            last_modified=int(path.stat().st_mtime * 1000),
        )

    @classmethod
    def from_bytes(
        cls,
        data: bytes,
        name: str,
        content_type: str | None = None,
        custom_id: str | None = None,
    ) -> "UTFile":
        """
        Create a UTFile from bytes.

        Args:
            data: The file content as bytes
            name: The filename
            content_type: Optional MIME type.
            custom_id: Optional custom identifier.

        Returns:
            A new UTFile instance
        """
        return cls(
            content=data,
            name=name,
            content_type=content_type,
            custom_id=custom_id,
        )

    def __repr__(self) -> str:
        return f"UTFile(name={self.name!r}, size={self.size}, type={self.content_type!r})"
