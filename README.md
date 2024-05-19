# Installation

```sh
pip install uploadthing.py
```

# Quickstart

```py
import asyncio, os

from uploadthing_py import UTApi


async def main():
    utapi = UTApi(os.environ["UTAPI_KEY"])

    # List the files in your app
    res = await utapi.list_files()
    print("List files:", res)

    # Delete the first file from the list
    key = res[0].key
    res = await utapi.delete_file(key)
    print("Delete file:", res)

    # (TODO) Create a new file
    # res = await utapi.upload_files()


if __name__ == "__main__":
    asyncio.run(main())
```
