# UploadThing Python SDK

A Python SDK for [UploadThing](https://uploadthing.com) - the easiest way to add file uploads to your app.

## Installation

```sh
pip install uploadthing.py
```

## Quick Start

### Setting up your token

The SDK uses the `UPLOADTHING_TOKEN` environment variable. You can get this from your UploadThing dashboard.

```bash
export UPLOADTHING_TOKEN="your-token-here"
```

### Using UTApi

```python
import asyncio
import os

from uploadthing_py import UTApi, UTFile, UploadFiles


async def main():
    # Initialize the client (reads UPLOADTHING_TOKEN from env)
    utapi = UTApi()

    # Upload a file from bytes
    file = UTFile.from_bytes(b"Hello, World!", "hello.txt")
    result = await utapi.upload_files(file)

    if result.is_success:
        print(f"Uploaded: {result.data.url}")
    else:
        print(f"Error: {result.error.message}")

    # Upload from a local file
    file = UTFile.from_path("./image.png")
    result = await utapi.upload_files(file)

    # Upload from a URL
    result = await utapi.upload_files_from_url(
        "https://example.com/image.png"
    )

    # Upload multiple files concurrently
    files = [
        UTFile.from_bytes(b"File 1", "file1.txt"),
        UTFile.from_bytes(b"File 2", "file2.txt"),
    ]
    results = await utapi.upload_files(
        files,
        options=UploadFiles.UploadFilesOptions(concurrency=2)
    )

    # List files in your app
    files = await utapi.list_files()
    for f in files:
        print(f"{f.name}: {f.key}")

    # Delete files
    await utapi.delete_files("file-key")

    # Generate signed URL for private files (no API call needed)
    signed = utapi.generate_signed_url("file-key")
    print(signed.ufs_url)


if __name__ == "__main__":
    asyncio.run(main())
```

## API Reference

### UTApi

The main client for interacting with UploadThing.

#### Constructor Options

```python
UTApi(
    token: str | None = None,        # UPLOADTHING_TOKEN (reads from env if not provided)
    key_type: str = "file_key",      # Default key type for operations
    api_url: str | None = None,      # Override API URL
    ingest_url: str | None = None,   # Override ingest URL
    ufs_host: str | None = None,     # Override UFS host
)
```

#### Methods

| Method                                 | Description                     |
| -------------------------------------- | ------------------------------- |
| `upload_files(files, options)`         | Upload files to UploadThing     |
| `upload_files_from_url(urls, options)` | Download from URLs and upload   |
| `delete_files(keys, options)`          | Delete files by key or customId |
| `list_files(options)`                  | List files in your app          |
| `rename_files(updates)`                | Rename files                    |
| `get_usage_info()`                     | Get storage usage stats         |
| `generate_signed_url(key, options)`    | Generate signed URL locally     |
| `get_signed_url(key, options)`         | Request signed URL via API      |
| `update_acl(keys, acl, options)`       | Update file access control      |

### UTFile

A file wrapper for uploads.

```python
# From bytes
file = UTFile.from_bytes(b"content", "name.txt")

# From file path
file = UTFile.from_path("./image.png")

# With custom ID
file = UTFile.from_bytes(b"content", "name.txt", custom_id="my-id")
```

### Upload Options

```python
UploadFiles.UploadFilesOptions(
    content_disposition="inline",  # or "attachment"
    acl="public-read",            # or "private"
    concurrency=1,                # Max concurrent uploads (1-25)
)
```

## Using with FastAPI

You can use this SDK with FastAPI for client-side uploads:

> [!WARNING]
> The FastAPI integration is experimental and not yet production-ready.

```python
from fastapi import FastAPI, Request, Response
from uploadthing_py import (
    UploadThingRequestBody,
    create_uploadthing,
    create_route_handler,
)
from fastapi.middleware.cors import CORSMiddleware
import os

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

f = create_uploadthing()

upload_router = {
    "imageUploader": f(
        {
            "image/png": {"max_file_size": "4MB"},
            "image/jpeg": {"max_file_size": "4MB"},
        }
    )
    .middleware(lambda req: {"user_id": req.headers.get("x-user-id")})
    .on_upload_complete(
        lambda file, metadata: print(f"Upload complete for {metadata['user_id']}")
    )
}

handlers = create_route_handler(
    router=upload_router,
    api_key=os.getenv("UPLOADTHING_SECRET"),  # Legacy API key for handlers
    is_dev=os.getenv("ENVIRONMENT", "development") == "development",
)


@app.get("/api/uploadthing")
async def ut_get():
    return handlers["GET"]()


@app.post("/api/uploadthing")
async def ut_post(
    request: Request,
    response: Response,
    body: UploadThingRequestBody,
):
    return await handlers["POST"](
        request=request,
        response=response,
        body=body,
    )
```

## Development

```bash
# Install dependencies
poetry install

# Run tests
poetry run pytest

# Run example
UPLOADTHING_TOKEN="your-token" poetry run python examples/upload_example.py

# Type checking
poetry run mypy uploadthing_py

# Linting
poetry run ruff check uploadthing_py
```

## License

MIT
