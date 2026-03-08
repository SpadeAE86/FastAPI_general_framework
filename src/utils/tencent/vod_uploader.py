import time
from typing import Optional, Dict, List, Any

from tencentcloud.common import credential
from tencentcloud.common.profile.client_profile import ClientProfile
from tencentcloud.common.profile.http_profile import HttpProfile
from tencentcloud.common.exception.tencent_cloud_sdk_exception import TencentCloudSDKException
from tencentcloud.vod.v20180717 import vod_client, models
from qcloud_cos import CosConfig
from qcloud_cos import CosS3Client
import sys
import os
import logging
from utils.log_utils import logger as log
import os
import json
import types


class TencentVodUploader:
    def __init__(
        self,
        secret_id: Optional[str] = None,
        secret_key: Optional[str] = None,
        region: str = "",
        sub_app_id: Optional[int] = None,
        endpoint: str = "vod.tencentcloudapi.com",
    ):
        """
        :param secret_id: 腾讯云 SecretId（默认从环境变量读）
        :param secret_key: 腾讯云 SecretKey（默认从环境变量读）
        :param region: VOD region，一般留空 ""
        :param sub_app_id: 点播子应用 ID
        """
        self.secret_id = secret_id or os.getenv("TENCENTCLOUD_SECRET_ID")
        self.secret_key = secret_key or os.getenv("TENCENTCLOUD_SECRET_KEY")
        self.sub_app_id = sub_app_id

        if not self.secret_id or not self.secret_key:
            raise RuntimeError("TencentCloud SecretId / SecretKey 未设置")

        cred = credential.Credential(self.secret_id, self.secret_key)

        http_profile = HttpProfile()
        http_profile.endpoint = endpoint

        client_profile = ClientProfile()
        client_profile.httpProfile = http_profile

        self.client = vod_client.VodClient(cred, "ap-shanghai", client_profile)

    # -----------------------------
    # 1. 申请上传
    # -----------------------------
    def apply_upload(self, video_path, media_type: str = "mp4") -> Dict:
        """
        调用 ApplyUpload，获取上传凭证
        """
        req = models.ApplyUploadRequest()
        media_name = os.path.basename(video_path)
        params = {
            "MediaName": media_name,
            "MediaType": media_type,
            "Procedure": "CommonTranscode",
        }
        if self.sub_app_id:
            params["SubAppId"] = self.sub_app_id

        req.from_json_string(json.dumps(params))

        print(f"apply_request: {req}")

        resp = self.client.ApplyUpload(req)

        return json.loads(resp.to_json_string())

    # -----------------------------
    # 2. 确认上传
    # -----------------------------
    def commit_upload(self, vod_session_key: str) -> Dict:
        """
        调用 CommitUpload，确认上传完成
        """
        req = models.CommitUploadRequest()
        params = {
            "VodSessionKey": vod_session_key,
        }
        if self.sub_app_id:
            params["SubAppId"] = self.sub_app_id

        req.from_json_string(json.dumps(params))
        resp = self.client.CommitUpload(req)

        return json.loads(resp.to_json_string())

    # -----------------------------
    # 3. 提交并轮询（工程版）
    # -----------------------------
    def commit_and_poll(
        self,
        vod_session_key: str,
        max_retry: int = 5,
        interval: float = 1.0,
    ) -> Dict:
        """
        提交上传并轮询，直到拿到 MediaUrl
        """
        last_exception = None
        print(f"start waiting for commit")
        for i in range(max_retry):

            try:
                result = self.commit_upload(vod_session_key)
                if result.get("MediaUrl"):
                    return result
            except TencentCloudSDKException as e:
                last_exception = e

            time.sleep(interval)

        if last_exception:
            raise last_exception
        raise RuntimeError("CommitUpload 超时，未获取到 MediaUrl")

    def describe_media_infos(
            self,
            file_id: str,
            filters: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        调用 DescribeMediaInfos 获取媒体详情（含转码信息）
        """
        req = models.DescribeMediaInfosRequest()

        params = {
            "FileIds": [file_id],
        }

        if filters:
            params["Filters"] = filters

        if self.sub_app_id:
            params["SubAppId"] = self.sub_app_id

        req.from_json_string(json.dumps(params))

        resp = self.client.DescribeMediaInfos(req)
        resp_json = json.loads(resp.to_json_string())
        log.info(f"media info resp: {resp_json}")

        media_info_set = resp_json.get("MediaInfoSet", [])
        if not media_info_set:
            raise RuntimeError(f"DescribeMediaInfos 未返回 MediaInfoSet, file_id={file_id}")

        return media_info_set[0]


def describe_transcode_info():
    tencent_uploader = TencentVodUploader(
        secret_id=os.getenv("TENCENTCLOUD_SECRET_ID", ""),
        secret_key=os.getenv("TENCENTCLOUD_SECRET_KEY", ""), 
        sub_app_id=1394787485
    )

    file_id = "5145403714210262892"

    # 只拉转码信息，减少 payload
    media_info = tencent_uploader.describe_media_infos(
        file_id=file_id,
        filters=["transcodeInfo", "snapshotByTimeOffsetInfo"]
    )

    print("=== DescribeMediaInfos (TranscodeInfo only) ===")
    print(json.dumps(media_info, indent=2, ensure_ascii=False))
    transcode_info = media_info.get("TranscodeInfo", {})
    transcode_set = transcode_info.get("TranscodeSet", [])
    log.info(f"returned len: {len(transcode_set)}")

    return media_info


if __name__ == "__main__":
    # tencent_uploader = TencentVodUploader(secret_id=os.getenv("TENCENTCLOUD_SECRET_ID"), secret_key=os.getenv("TENCENTCLOUD_SECRET_KEY"), sub_app_id= 1394787485)
    # video_path = r"/test/test2.mp4"
    # apply_resp = tencent_uploader.apply_upload(video_path=video_path, media_type="mp4")
    # print("upload request success:", apply_resp)
    #
    # vod_upload_to_cos(apply_resp, video_path)
    #
    # task_id = apply_resp["VodSessionKey"]
    # transcode_result = tencent_uploader.commit_and_poll(task_id)
    # print(transcode_result)
    describe_transcode_info()
