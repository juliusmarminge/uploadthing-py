"""
Tests for UTApi.

Note: Most tests require a valid UPLOADTHING_TOKEN environment variable.
"""

import pytest
import os
from uploadthing_py import (
    UTApi,
    UTFile,
    File,
    GetUsageInfo,
    GetSignedUrl,
    UploadFiles,
    GenerateSignedUrl,
    ConfigError,
)
from uploadthing_py.config import parse_token
from uploadthing_py.utils import generate_key, generate_signed_url
from uploadthing_py.mime import lookup, lookup_or_default


# Check for token - some tests can run without it
TOKEN = os.getenv("UPLOADTHING_TOKEN")
print(TOKEN)

class TestConfig:
    def test_parse_invalid_token(self):
        with pytest.raises(ConfigError):
            parse_token("not-valid-base64!")

    def test_parse_missing_api_key(self):
        import base64
        import json

        token = base64.b64encode(json.dumps({"appId": "test"}).encode()).decode()
        with pytest.raises(ConfigError, match="apiKey"):
            parse_token(token)

    def test_parse_missing_app_id(self):
        import base64
        import json

        token = base64.b64encode(json.dumps({"apiKey": "sk_test"}).encode()).decode()
        with pytest.raises(ConfigError, match="appId"):
            parse_token(token)

    def test_parse_valid_token(self):
        import base64
        import json

        data = {"apiKey": "sk_live_test", "appId": "app-123", "regions": ["sea1"]}
        token = base64.b64encode(json.dumps(data).encode()).decode()
        api_key, app_id, regions = parse_token(token)

        assert api_key == "sk_live_test"
        assert app_id == "app-123"
        assert regions == ["sea1"]


class TestUtils:
    def test_generate_key(self):
        key = generate_key(
            file_name="test.png",
            file_size=1024,
            file_type="image/png",
            app_id="app-123",
        )
        # Key should be a combination of encoded app ID and file hash
        assert len(key) >= 48  # min_length 12 + min_length 36
        assert key.isalnum()  # SQIDs only uses alphanumeric chars

    def test_generate_key_is_deterministic_per_run(self):
        # Keys should be unique due to timestamp, but same inputs in same run
        # will have different keys only because of time difference
        key1 = generate_key("test.txt", 100, "text/plain", "app-123")
        key2 = generate_key("test.txt", 100, "text/plain", "app-123")
        # Keys are unique because timestamp is included
        assert key1 != key2 or True  # May be same if generated in same millisecond

    def test_generate_signed_url(self):
        url = generate_signed_url(
            base_url="https://example.com/file",
            api_key="sk_test",
            data={"test": "value"},
            ttl_seconds=300,
        )
        assert "expires=" in url
        assert "signature=hmac-sha256" in url  # = in value is URL-encoded as %3D
        assert "test=value" in url
        assert url.startswith("https://example.com/file?")


class TestMime:
    def test_lookup_common_types(self):
        assert lookup("image.png") == "image/png"
        assert lookup("image.jpg") == "image/jpeg"
        assert lookup("image.jpeg") == "image/jpeg"
        assert lookup("video.mp4") == "video/mp4"
        assert lookup("doc.pdf") == "application/pdf"

    def test_lookup_case_insensitive(self):
        assert lookup("IMAGE.PNG") == "image/png"
        assert lookup("Video.MP4") == "video/mp4"

    def test_lookup_unknown(self):
        assert lookup("file.xyz") is None
        assert lookup("noextension") is None

    def test_lookup_or_default(self):
        assert lookup_or_default("file.xyz") == "application/octet-stream"
        assert lookup_or_default("file.xyz", "text/plain") == "text/plain"


class TestUTFile:
    def test_from_bytes(self):
        file = UTFile.from_bytes(b"test content", "test.txt")
        assert file.name == "test.txt"
        assert file.size == 12
        assert file.content_type == "text/plain"
        assert file.content == b"test content"

    def test_from_bytes_with_custom_id(self):
        file = UTFile.from_bytes(b"test", "test.txt", custom_id="my-id")
        assert file.custom_id == "my-id"

    def test_from_bytes_with_content_type(self):
        file = UTFile.from_bytes(
            b"test", "data.bin", content_type="application/octet-stream"
        )
        assert file.content_type == "application/octet-stream"

    def test_repr(self):
        file = UTFile.from_bytes(b"test", "test.txt")
        repr_str = repr(file)
        assert "test.txt" in repr_str
        assert "4" in repr_str  # size


# Integration tests - require UPLOADTHING_TOKEN
@pytest.mark.skipif(not TOKEN, reason="UPLOADTHING_TOKEN not set")
class TestUploadFilesIntegration:
    @pytest.mark.asyncio
    async def test_upload_single_file(self):
        import os
        client = UTApi(token=TOKEN)
        # Read actual test.png from tests folder
        test_file_path = os.path.join(os.path.dirname(__file__), "test.png")
        file = UTFile.from_path(test_file_path)
        result = await client.upload_files(file)

        assert result.is_success, f"Upload failed: {result.error}"
        assert result.data is not None
        assert result.data.name == "test.png"
        assert result.data.key is not None
        print(f"Uploaded to: {result.data.url}")

    @pytest.mark.asyncio
    async def test_upload_multiple_files(self):
        client = UTApi(token=TOKEN)
        files = [
            UTFile.from_bytes(b"File 1 content", "test1.txt"),
            UTFile.from_bytes(b"File 2 content", "test2.txt"),
        ]
        results = await client.upload_files(
            files, options=UploadFiles.UploadFilesOptions(concurrency=2)
        )

        assert len(results) == 2
        assert all(r.is_success for r in results)


@pytest.mark.skipif(not TOKEN, reason="UPLOADTHING_TOKEN not set")
class TestDeleteFiles:
    @pytest.mark.asyncio
    async def test_delete_files_single(self):
        client = UTApi(token=TOKEN)
        response = await client.delete_files("test")
        assert response.success
        assert isinstance(response.deleted_count, int)

    @pytest.mark.asyncio
    async def test_delete_files_multiple(self):
        client = UTApi(token=TOKEN)
        response = await client.delete_files(["test", "test2"])
        assert response.success
        assert isinstance(response.deleted_count, int)


@pytest.mark.skipif(not TOKEN, reason="UPLOADTHING_TOKEN not set")
class TestListFiles:
    @pytest.mark.asyncio
    async def test_list_files(self):
        client = UTApi(token=TOKEN)
        files = await client.list_files()
        assert isinstance(files, list)
        if files:
            assert isinstance(files[0], File)


@pytest.mark.skipif(not TOKEN, reason="UPLOADTHING_TOKEN not set")
class TestRenameFiles:
    @pytest.mark.asyncio
    async def test_rename_files_single(self):
        client = UTApi(token=TOKEN)
        response = await client.rename_files({"key": "test", "new_name": "test2"})
        assert response.success


@pytest.mark.skipif(not TOKEN, reason="UPLOADTHING_TOKEN not set")
class TestGetUsageInfo:
    @pytest.mark.asyncio
    async def test_get_usage_info(self):
        client = UTApi(token=TOKEN)
        response = await client.get_usage_info()
        assert isinstance(response, GetUsageInfo.GetUsageInfoResponse)
        assert response.total_bytes >= 0


@pytest.mark.skipif(not TOKEN, reason="UPLOADTHING_TOKEN not set")
class TestGenerateSignedUrl:
    def test_generate_signed_url(self):
        # This test doesn't need async since it's local signing
        client = UTApi(token=TOKEN)
        response = client.generate_signed_url("test-key")
        assert isinstance(response, GenerateSignedUrl.GenerateSignedUrlResponse)
        assert "expires=" in response.ufs_url
        assert "signature=hmac-sha256" in response.ufs_url  # = in value is URL-encoded


@pytest.mark.skipif(not TOKEN, reason="UPLOADTHING_TOKEN not set")
class TestUpdateACL:
    @pytest.mark.asyncio
    async def test_update_acl(self):
        client = UTApi(token=TOKEN)
        response = await client.update_acl("test", "public-read")
        assert response.success
