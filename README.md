# Installation

```sh
pip install uploadthing.py
```

# Quickstart

## Using UTApi

This is basically a 1:1 clone of the official [TypeScript SDK](https://docs.uploadthing.com/api-reference/ut-api)

```py
import asyncio, os

from uploadthing_py import UTApi


async def main():
    utapi = UTApi(os.getenv("UPLOADTHING_SECRET"))

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

## Using FastAPI

You can use FastAPI like any of the JavaScript backend adapters.

> [!TIP]
>
> You can use this example along with one of the [client examples](https://github.com/pingdotgg/uploadthing/tree/main/examples/backend-adapters)
>
> ```sh
> UPLOADTHING_SECRET=sk_foo poetry run uvicorn examples.fastapi:app --reload --port 3000
> ```

> [!WARNING]
>
> This is a work in progress and not yet ready for production use.

```py
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
    "videoAndImage": f(
        {
            "image/png": {"max_file_size": "4MB"},
            "image/heic": {"max_file_size": "16MB"},
        }
    )
    .middleware(lambda req: {"user_id": req.headers["x-user-id"]})
    .on_upload_complete(lambda file, metadata: print(f"Upload complete for {metadata['user_id']}"))
}
handlers = create_route_handler(
    router=upload_router,
    api_key=os.getenv("UPLOADTHING_SECRET"),
    is_dev=os.getenv("ENVIRONMENT", "development") == "development",
)


@app.get("/api")
async def greeting():
    return "Hello from FastAPI"


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
