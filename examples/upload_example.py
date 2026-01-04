"""
Example: Upload files using UTApi.

This example demonstrates how to upload files to UploadThing using the Python SDK.

Requirements:
    - Set UPLOADTHING_TOKEN environment variable with your token

Usage:
    poetry run python examples/upload_example.py
"""

import asyncio
import os
from pathlib import Path

from uploadthing_py import UTApi, UTFile, UploadFiles


async def main():
    # Initialize the client (reads UPLOADTHING_TOKEN from environment)
    utapi = UTApi()
    print(f"Connected to app: {utapi.app_id}")

    # Example 1: Upload a file from bytes
    print("\n--- Example 1: Upload from bytes ---")
    content = b"Hello, UploadThing!"
    file = UTFile.from_bytes(content, "hello.txt")
    result = await utapi.upload_files(file)

    if result.is_success:
        print(f"✅ Uploaded: {result.data.name}")
        print(f"   URL: {result.data.ufs_url}")
        print(f"   Key: {result.data.key}")
    else:
        print(f"❌ Error: {result.error.message}")

    # Example 2: Upload multiple files concurrently
    print("\n--- Example 2: Upload multiple files ---")
    files = [
        UTFile.from_bytes(b"File 1 content", "file1.txt"),
        UTFile.from_bytes(b"File 2 content", "file2.txt"),
        UTFile.from_bytes(b"File 3 content", "file3.txt"),
    ]
    results = await utapi.upload_files(
        files,
        options=UploadFiles.UploadFilesOptions(concurrency=3),
    )

    for r in results:
        if r.is_success:
            print(f"✅ {r.data.name} -> {r.data.ufs_url}")
        else:
            print(f"❌ Error: {r.error.message}")

    # Example 3: Upload from a local file path
    print("\n--- Example 3: Upload from file path ---")
    # Create a temp file for demo
    temp_file = Path("temp_upload_test.txt")
    temp_file.write_text("This is a test file for upload.")

    try:
        file = UTFile.from_path(temp_file)
        result = await utapi.upload_files(file)

        if result.is_success:
            print(f"✅ Uploaded: {result.data.name}")
            print(f"   URL: {result.data.ufs_url}")
        else:
            print(f"❌ Error: {result.error.message}")
    finally:
        temp_file.unlink()  # Clean up

    # Example 4: Upload from URL
    print("\n--- Example 4: Upload from URL ---")
    result = await utapi.upload_files_from_url(
        "https://via.placeholder.com/150"
    )

    if result.is_success:
        print(f"✅ Uploaded: {result.data.name}")
        print(f"   URL: {result.data.ufs_url}")
    else:
        print(f"❌ Error: {result.error.message}")

    # Example 5: Generate signed URL for private file access
    print("\n--- Example 5: Generate signed URL ---")
    if result.is_success:
        signed = utapi.generate_signed_url(result.data.key)
        print(f"Signed URL (valid for 5 min): {signed.ufs_url[:80]}...")

    # Example 6: List and manage files
    print("\n--- Example 6: List files ---")
    files = await utapi.list_files()
    print(f"Total files in app: {len(files)}")
    for f in files[:3]:  # Show first 3
        print(f"  - {f.name} ({f.key})")


if __name__ == "__main__":
    asyncio.run(main())
