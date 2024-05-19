import pytest
from uploadthing_py import UTApi, File, GetUsageInfo, GetSignedUrl

API_KEY = "sk_"


class TestDeleteFiles:
    @pytest.mark.asyncio
    async def test_delete_files_single(self):
        client = UTApi(API_KEY)
        response = await client.delete_files("test")
        assert response.success

    @pytest.mark.asyncio
    async def test_delete_files_multiple(self):
        client = UTApi(API_KEY)
        response = await client.delete_files(["test", "test2"])
        assert response.success


class TestListFiles:
    @pytest.mark.asyncio
    async def test_list_files_single(self):
        client = UTApi(API_KEY)
        file, *_ = await client.list_files()
        assert isinstance(file, File)


class TestRenameFiles:
    @pytest.mark.asyncio
    async def test_rename_files_single(self):
        client = UTApi(API_KEY)
        response = await client.rename_files({"key": "test", "new_name": "test2"})
        assert response.success

    @pytest.mark.asyncio
    async def test_rename_files_multiple(self):
        client = UTApi(API_KEY)
        response = await client.rename_files(
            [
                {"key": "test", "new_name": "test2"},
                {"key": "test3", "new_name": "test4"},
            ]
        )
        assert response.success


class TestGetUsageInfo:
    @pytest.mark.asyncio
    async def test_get_usage_info(self):
        client = UTApi(API_KEY)
        response = await client.get_usage_info()
        assert isinstance(response, GetUsageInfo.GetUsageInfoResponse)


class TestGetSignedUrl:
    @pytest.mark.asyncio
    async def test_get_signed_url(self):
        client = UTApi(API_KEY)
        response = await client.get_signed_url("test")
        assert isinstance(response, GetSignedUrl.GetSignedUrlResponse)


class TestUpdateACL:
    @pytest.mark.asyncio
    async def test_update_acl(self):
        client = UTApi(API_KEY)
        response = await client.update_acl("test", "public-read")
        assert response.success
