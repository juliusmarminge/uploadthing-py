"""
Simple example of using the library.
"""

import asyncio
import os

from uploadthing_py import UTApi, UTFile


async def main():
    utapi = UTApi()

    # List the files in your app
    res = await utapi.list_files()
    print("List files:", res)

    # Upload a file
    file = UTFile.from_bytes(b"Hello from Python!", "hello.txt")
    result = await utapi.upload_files(file)
    
    if result.is_success:
        print("Upload success:", result.data.url)
        
        # Delete the uploaded file
        res = await utapi.delete_files(result.data.key)
        print("Delete file:", res)
    else:
        print("Upload error:", result.error.message)


if __name__ == "__main__":
    asyncio.run(main())
