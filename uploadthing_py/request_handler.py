from fastapi import Request, Response
from httpx import AsyncClient
from uploadthing_py.utils import (
    json_stringify,
    sign_payload,
    verify_signature,
    generate_key,
    generate_signed_url,
)
from uploadthing_py.builder import UploadThingBuilder
from asyncio import create_task, sleep
from uploadthing_py.types import (
    UploadRequest,
    CallbackRequest,
    CompleteMPURequest,
    UploadThingToken,
)
import typing as t


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


async def dev_hook(presigned: dict, token: UploadThingToken):
    retry_delay = 40e-3
    async with AsyncClient() as client:
        while True:
            response = await client.get(
                presigned["pollingUrl"],
                headers={
                    "Authorization": presigned["pollingJwt"],
                    "x-uploadthing-api-key": token.api_key,
                    "x-uploadthing-version": "6.10.0",
                },
            )
            polling_data = response.json()
            if polling_data["status"] == "done":
                print("[DEV_HOOK] Polling done")
                break
            await sleep(retry_delay)
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

        signature = sign_payload(payload, token.api_key)

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
    token: UploadThingToken,
    is_dev: bool,
    callback_url: str | None = None,
):
    # Run middleware to verify permission to upload
    try:
        metadata = uploader.callbacks["middleware"](request)
    except Exception as e:
        print("Middleware error", e)
        return {"error": "Unauthorized"}

    callback_url = (
        callback_url or f"{request.url.scheme}://{request.url.netloc}{request.url.path}"
    )
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

    ingest_url = f"https://{token.regions[0]}.{token.ingest_host}"

    presigned_urls: t.List[t.Dict[str, str]] = []
    for file in files:
        key = generate_key(file, token.app_id)
        url = f"{ingest_url}/{key}"
        data = {
            "x-ut-identifier": token.app_id,
            "x-ut-file-name": file["name"],
            "x-ut-file-size": file["size"],
            "x-ut-file-type": file["type"],
            # "x-ut-custom-id": None,
            "x-ut-content-disposition": file["contentDisposition"],
            "x-ut-acl": file["acl"] if "acl" in file else "public-read",
        }
        signed_url = generate_signed_url(url, token.api_key, data=data)
        presigned_urls.append(
            {"url": signed_url, "key": key, "customId": None, "name": file["name"]}
        )

    # TODO: Dev hook

    async def register_upload():
        payload = json_stringify(
            {
                "fileKeys": [url["key"] for url in presigned_urls],
                "metadata": metadata,
                "isDev": is_dev,
                "callbackUrl": callback_url,
                "callbackSlug": slug,
                "awaitServerData": False,  # TODO: Add support
            }
        )
        async with AsyncClient() as client:
            print("[metadata request]: Sending payload", payload)
            try:
                response = await client.post(
                    f"{ingest_url}/route-metadata",
                    content=payload,
                    headers={
                        "x-uploadthing-api-key": token.api_key,
                        "x-uploadthing-version": "7.0.0",
                        "x-uploadthing-be-adapter": "uploadthing.py@",
                        "Content-Type": "application/json",
                    },
                )
                print("[metadata request]: Got response", response)
            except Exception as e:
                print("[metadata request]: Got error", e)

    # Register upload in background
    create_task(register_upload())

    print("Sending presigneds to client", presigned_urls)

    return presigned_urls


async def handle_callback_request(
    uploader: UploadThingBuilder,
    request: Request,
    body: CallbackRequest,
    token: UploadThingToken,
):
    if not verify_signature(
        (await request.body()).decode("utf-8"),
        request.headers["x-uploadthing-signature"],
        token.api_key,
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
                "x-uploadthing-api-key": token.api_key,
                "x-uploadthing-version": "6.10.0",
            },
        )
        print("[CALLBACK]", response.status_code, response.text)

        return {"success": True}


def create_route_handler(
    router: dict[str, UploadThingBuilder],
    token: str,
    is_dev: bool,
    callback_url: str | None = None,
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
        body: t.Union[UploadRequest, CallbackRequest, CompleteMPURequest],
    ):
        if not token:
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

        decoded_token = UploadThingToken.parse(token)

        match [uploadthing_hook, action_type]:
            case ["callback", None]:
                return await handle_callback_request(
                    uploader=uploader, request=request, body=body, token=decoded_token
                )
            case [None, "upload"]:
                return await handle_upload_request(
                    uploader=uploader,
                    request=request,
                    body=body,
                    slug=slug,
                    token=decoded_token,
                    is_dev=is_dev,
                    callback_url=callback_url,
                )
            case _:
                response.status_code = 400
                return {
                    "error": "Bad request. Invalid hook header or actionType parameter"
                }

    return {"GET": ut_get, "POST": ut_post}
