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


def middleware(req: Request):
    print("Authenticating request")
    return {"userId": "1234"}


def callback(file, metadata):
    print(f"Callback called for {metadata['userId']}")
    return {"success": True, "haha": "we've got a Python SDK now"}


upload_router = {
    "videoAndImage": f(
        {
            "image/png": {"max_file_size": "4MB"},
            "image/heic": {"max_file_size": "16MB"},
        }
    )
    .middleware(middleware)
    .on_upload_complete(callback)
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
