from typing import Callable


class UploadThingBuilder:
    def __init__(self):
        self.config = {}
        self.callbacks = {
            "middleware": lambda req: None,
            "on_upload_error": lambda req, err: None,
            "on_upload_complete": lambda req, metadata, file: None,
        }

    def __call__(self, config):
        self.config.update(config)
        return self

    def middleware(self, func: Callable):
        self.callbacks["middleware"] = func
        return self

    def on_upload_error(self, func: Callable):
        self.callbacks["on_upload_error"] = func
        return self

    def on_upload_complete(self, func: Callable):
        self.callbacks["on_upload_complete"] = func
        return self


def create_uploadthing():
    """
    Builder for creating a new UploadThing file route

    ### Example usage:
    ```py
    f = create_uploadthing()

    def image_auth_middleware(req: Request):
        return {"userId": "1234"}

    upload_router = {
        "videoAndImage": f({"image": {"max_file_size": "4MB"}})
        .middleware(image_auth_middleware)
        .on_upload_complete(
            lambda metadata, file: print(
                f"Upload complete for userId: {metadata['userId']}"
            )
        )
    }
    ```
    """
    return UploadThingBuilder()
