from fastapi import Request, Response
from httpx import AsyncClient
from uploadthing_py.utils import json_stringify, sign_payload, verify_signature
from uploadthing_py.builder import UploadThingBuilder
import asyncio
from uploadthing_py.types import (
    UploadRequest,
    CallbackRequest,
    CompleteMPURequest,
    FailureRequest,
)
from typing import Union


def extract_router_config(router: dict[str, UploadThingBuilder]):
    routes = []
    for slug, config in router.items():
        route_config = {"slug": slug, "config": {}}

        for file_type, type_options in config.config.items():
            conf = route_config["config"][file_type] = {}
            conf["contentDisposition"] = (
                type_options["content_disposition"]
                if "content_disposition" in type_options
                else "attachment"
            )
            conf["maxFileSize"] = (
                type_options["max_file_size"]
                if "max_file_size" in type_options
                else "4MB"
            )
            conf["maxFileCount"] = (
                type_options["max_file_count"]
                if "max_file_count" in type_options
                else 1
            )
            conf["minFileCount"] = (
                type_options["min_file_count"]
                if "min_file_count" in type_options
                else 1
            )

        routes.append(route_config)
    return routes


async def dev_hook(presigned: dict, api_key: str):
    retry_delay = 40e-3
    async with AsyncClient() as client:
        while True:
            response = await client.get(
                presigned["pollingUrl"],
                headers={
                    "Authorization": presigned["pollingJwt"],
                    "x-uploadthing-api-key": api_key,
                    "x-uploadthing-version": "6.10.0",
                },
            )
            polling_data = response.json()
            if polling_data["status"] == "done":
                print("[DEV_HOOK] Polling done")
                break
            await asyncio.sleep(retry_delay)
            retry_delay *= 2

        file = polling_data["file"]
        callback_url = f"{file['callbackUrl']}?slug={file['callbackSlug']}"
        payload = json_stringify(
            {
                "status": "uploaded",
                "metadata": polling_data["metadata"],
                "file": {
                    "url": file["fileUrl"],
                    "key": file["fileKey"],
                    "name": file["fileName"],
                    "size": file["fileSize"],
                    "custom_id": file["customId"],
                    "type": file["fileType"],
                },
            }
        )

        signature = sign_payload(payload, api_key)

        callback_response = await client.post(
            callback_url,
            content=payload,
            headers={
                "Content-Type": "application/json",
                "uploadthing-hook": "callback",
                "x-uploadthing-signature": signature,
            },
        )
        print(
            "[DEV_HOOK CALLBACK]", callback_response.status_code, callback_response.text
        )


async def handle_upload_request(
    uploader: UploadThingBuilder,
    request: Request,
    body: UploadRequest,
    slug: str,
    api_key: str,
    is_dev: bool,
):
    # Run middleware to verify permission to upload
    try:
        metadata = uploader.callbacks["middleware"](request)
    except Exception as e:
        print("Middleware error", e)
        return {"error": "Unauthorized"}

    callback_url = f"{request.url.scheme}://{request.url.netloc}{request.url.path}"
    files = [
        {
            "name": file.name,
            "size": file.size,
            "type": file.type,
            "customId": None,  # (TODO) Add support
            "contentDisposition": (
                uploader.config["content-disposition"]
                if "content-disposition" in uploader.config
                else "inline"
            ),
            **({"acl": uploader.config["acl"]} if "acl" in uploader.config else {}),
        }
        for file in body.files
    ]

    payload = json_stringify(
        {
            "files": files,
            "metadata": metadata,
            "callbackUrl": callback_url,
            "callbackSlug": slug,
        }
    )
    async with AsyncClient() as client:
        response = await client.post(
            "https://api.uploadthing.com/v7/prepareUpload",
            content=payload,
            headers={
                "x-uploadthing-api-key": api_key,
                "x-uploadthing-be-adapter": "uploadthing.py@",
                "x-uploadthing-version": "6.10.0",
                "Content-Type": "application/json",
            },
        )
        print("[PRESIGNEDS]", response.status_code, response.text)
        if response.status_code != 200:
            return {"error": "Failed to get presigned URLs"}

        presigned_urls = response.json()["data"]

        if is_dev:
            asyncio.gather(
                *[dev_hook(presigned, api_key) for presigned in presigned_urls]
            )

        return presigned_urls


async def handle_callback_request(
    uploader: UploadThingBuilder, request: Request, body: CallbackRequest, api_key: str
):
    if not verify_signature(
        (await request.body()).decode("utf-8"),
        request.headers["x-uploadthing-signature"],
        api_key,
    ):
        return {"error": "Invalid signature"}

    try:
        server_data = uploader.callbacks["on_upload_complete"](
            file=body.file, metadata=body.metadata
        )
    except Exception as e:
        print("on_upload_complete error", e)
        return {"error": "Failed to run complete callback"}

    payload = json_stringify({"fileKey": body.file.key, "callbackData": server_data})
    async with AsyncClient() as client:
        response = await client.post(
            "https://api.uploadthing.com/v6/serverCallback",
            content=payload,
            headers={
                "Content-Type": "application/json",
                "x-uploadthing-api-key": api_key,
                "x-uploadthing-version": "6.10.0",
            },
        )
        print("[CALLBACK]", response.status_code, response.text)

        return {"success": True}


async def handle_complete_mpu_request(body: CompleteMPURequest, api_key: str):
    async with AsyncClient() as client:
        response = await client.post(
            "https://api.uploadthing.com/v6/completeMultipart",
            content=body.model_dump_json(),
            headers={
                "Content-Type": "application/json",
                "x-uploadthing-api-key": api_key,
                "x-uploadthing-version": "6.10.0",
            },
        )
        print("[MPU COMPLETE]", response.status_code, response.text)

        return {"success": True}


async def handle_failure_request(
    uploader: UploadThingBuilder, body: FailureRequest, api_key: str
):
    payload = json_stringify(
        {
            "fileKey": body.fileKey,
            "uploadId": body.uploadId,
        }
    )
    async with AsyncClient() as client:
        response = await client.post(
            "https://api.uploadthing.com/v6/failureCallback",
            content=payload,
            headers={
                "Content-Type": "application/json",
                "x-uploadthing-api-key": api_key,
                "x-uploadthing-version": "6.10.0",
            },
        )
        print("[MPU FAILURE]", response.status_code, response.text)

    try:
        uploader.callbacks["on_upload_error"](file_key=body.fileKey)
    except Exception as e:
        print("on_upload_error error", e)
        return {"error": "Failed to run error callback"}

    return {"success": True}


def create_route_handler(
    router: dict[str, UploadThingBuilder], api_key: str, is_dev: bool
):
    """
    Create request handlers for client side uploads

    ### Example usage:
    ```py
    from fastapi import FastAPI, Request, Response
    from uploadthing_py import (
        create_uploadthing,
        UploadThingRequestBody,
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
    """

    def ut_get():
        return extract_router_config(router)

    async def ut_post(
        request: Request,
        response: Response,
        body: Union[UploadRequest, CallbackRequest, CompleteMPURequest],
    ):
        if not api_key:
            response.status_code = 500
            return {"error": "No API key provided"}

        if "slug" not in request.query_params:
            response.status_code = 400
            return {"error": "Missing slug parameter"}
        slug = request.query_params["slug"]

        if slug not in router:
            response.status_code = 404
            return {"error": "Unknown uploader"}
        uploader = router[slug]

        action_type = (
            request.query_params["actionType"]
            if "actionType" in request.query_params
            else None
        )
        uploadthing_hook = (
            request.headers["uploadthing-hook"]
            if "uploadthing-hook" in request.headers
            else None
        )

        match [uploadthing_hook, action_type]:
            case ["callback", None]:
                return await handle_callback_request(
                    uploader=uploader, request=request, body=body, api_key=api_key
                )
            case [None, "upload"]:
                return await handle_upload_request(
                    uploader=uploader,
                    request=request,
                    body=body,
                    slug=slug,
                    api_key=api_key,
                    is_dev=is_dev,
                )
            case [None, "failure"]:
                return await handle_failure_request(
                    uploader=uploader, body=body, api_key=api_key
                )
            case [None, "multipart-complete"]:
                return await handle_complete_mpu_request(body=body, api_key=api_key)
            case _:
                response.status_code = 400
                return {
                    "error": "Bad request. Invalid hook header or actionType parameter"
                }

    return {"GET": ut_get, "POST": ut_post}
