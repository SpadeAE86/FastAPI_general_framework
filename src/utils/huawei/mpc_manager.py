# coding: utf-8
import asyncio
import os
import time
from typing import Optional, List

from huaweicloudsdkcore.auth.credentials import BasicCredentials
from huaweicloudsdkmpc.v1 import *
from huaweicloudsdkmpc.v1.region.mpc_region import MpcRegion
from huaweicloudsdkcore.exceptions import exceptions
from utils.log_utils import logger as log
from models.pydantic_dataclass.transcode_output import VideoStreamMeta, DynamicRangeInfo, AudioStreamMeta, \
    TranscodeOutput


class HuaweiMPCClient:
    def __init__(self, ak: str = None, sk: str = None, region: str = "cn-east-3"):
        """
        初始化华为云 MPC 客户端
        :param ak: 华为云 Access Key
        :param sk: 华为云 Secret Key
        :param region: MPC 区域
        """

        self.ak = 'UJDPK31ANIBV0XTEUN5N'
        self.sk = 'NhQExxv9PUYsvmvGnVReizRksaiHcJdQ6vMMw19d'
        self.region = "cn-east-3"

        credentials = BasicCredentials(self.ak, self.sk)
        self.client = MpcClient.new_builder() \
            .with_credentials(credentials) \
            .with_region(MpcRegion.value_of(region)) \
            .build()

    def create_thumbnail_sync(
        self,
        input_bucket: str,
        input_object: str,
        output_bucket: str,
        output_object_prefix: str,
        thumbnail_time_ms: int = 0,
        short_edge: int = 360,
        user_data: str = None
    ) -> Optional[str]:
        """
        同步截图方法
        :param input_bucket: 视频所在桶
        :param input_object: 视频完整路径
        :param output_bucket: 输出截图桶
        :param output_object_prefix: 输出目录前缀（不含文件名）
        :param thumbnail_time_ms: 截图时间点（毫秒）
        :param short_edge: 截图短边尺寸
        :param user_data: 用户自定义信息
        :return: None或者完整截图路径（object + 文件名）
        """
        # 构建截图参数
        thumbnail_para = ThumbnailPara(
            type="DOTS_MS",
            dots_ms=[thumbnail_time_ms],
            max_length=short_edge
        )

        # 输入信息
        input_info = ObsObjInfo(
            bucket=input_bucket,
            location=self.region,
            object=input_object
        )

        # 输出信息（不传 file_name，MPC 自动生成）
        output_info = ObsObjInfo(
            bucket=output_bucket,
            location=self.region,
            object=output_object_prefix,
            file_name="cover_img"
        )

        # 构建请求
        request = CreateThumbnailsTaskRequest()
        request.body = CreateThumbReq(
            original_dir=1,   # 输出目录可随机，避免覆盖
            sync=1,           # 同步截图
            tar=1,            # 是否打包，这里默认 1（不压缩）
            thumbnail_para=thumbnail_para,
            user_data=user_data,
            input=input_info,
            output=output_info
        )

        try:
            response = self.client.create_thumbnails_task(request)
            # 返回完整截图路径
            object_path = response.output.object
            file_name = response.output_file_name
            return f"{object_path}{file_name}"
        except exceptions.ClientRequestException as e:
            print(f"Error: {e.error_msg}, code: {e.error_code}, status: {e.status_code}")
            return None

    def create_transcoding_task(
            self,
            input_bucket: str,
            input_object: str,
            output_bucket: str,
            output_object_prefix: str,
            template_ids: list[int]
    ) -> Optional[str]:
        """
        创建转码任务
        :param input_bucket: 输入视频桶
        :param input_object: 输入视频路径
        :param output_bucket: 输出桶
        :param output_object_prefix: 输出目录前缀
        :param template_ids: 转码模板 ID 列表
        :return: None或者任务 ID
        """
        log.info(
            f"{input_bucket} -> {input_object}, {output_bucket} -> {output_object_prefix}")

        input_info = ObsObjInfo(
            bucket=input_bucket,
            location=self.region,
            object=input_object
        )

        output_info = ObsObjInfo(
            bucket=output_bucket,
            location=self.region,
            object=output_object_prefix,
            file_name="transcode"
        )

        body = CreateTranscodingReq(
            input=input_info,
            output=output_info,
            trans_template_id=template_ids
        )

        request = CreateTranscodingTaskRequest()
        request.body = body

        try:
            response = self.client.create_transcoding_task(request)
            return str(response.task_id)
        except exceptions.ClientRequestException as e:
            print(f"Error: {e.error_msg}, code: {e.error_code}, status: {e.status_code}")
            return None

    # ----------------------
    # 获取转码任务状态
    # ----------------------
    def get_transcoding_task_status(self, task_id: int):
        """
        获取转码任务状态
        :param task_id: MPC 转码任务 ID
        :return: 任务原始响应 JSON
        """
        request = ListTranscodingTaskRequest()
        request.task_id = [task_id]
        response = self.client.list_transcoding_task(request)
        if response.total > 0:
            return response.task_array[0]
        return None

    # ----------------------
    # 轮询任务直至成功
    # ----------------------
    async def wait_transcoding_success(
            self,
            task_id: int,
            poll_interval: int = 5,
            timeout: int = 1400
    ) -> Optional[List[TranscodeOutput]]:
        """
        轮询转码任务，直到状态为 SUCCEEDED
        :param task_id: 转码任务 ID
        :param poll_interval: 轮询间隔秒
        :param timeout: 超时时间秒
        :return: 转码输出列表，任务成功时返回
        """
        start_time = time.time()
        while True:
            task_info = self.get_transcoding_task_status(task_id)
            if task_info is None:
                raise ValueError(f"Task {task_id} 不存在或获取失败")
            status = task_info.status
            if status == "SUCCEEDED":
                # 解析输出文件
                outputs = []
                for idx, multi in enumerate(task_info.transcode_detail.multitask_info):
                    output_file = multi.output_file
                    video_meta = None
                    audio_meta = None
                    if output_file.video_info:
                        video_info = output_file.video_info
                        dr_info = DynamicRangeInfo(type=getattr(video_info, "dynamic_range", None))
                        video_meta = VideoStreamMeta(
                            codec=getattr(video_info, "codec", None),
                            width=getattr(video_info, "width", None),
                            height=getattr(video_info, "height", None),
                            fps=getattr(video_info, "frame_rate", None),
                            bitrate=getattr(video_info, "bitrate_bps", None),
                            dynamic_range=dr_info
                        )
                    if output_file.audio_info:
                        ainfo = output_file.audio_info[0]
                        audio_meta = AudioStreamMeta(
                            codec=getattr(ainfo, "codec", None),
                            sampling_rate=getattr(ainfo, "sample", None),
                            bitrate=getattr(ainfo, "bitrate_bps", None)
                        )

                    # 拼 URL：用任务顶层 output + 对应 output_file_name
                    file_name = task_info.output_file_name[idx]
                    url = f"{task_info.output.object}/{file_name}"

                    outputs.append(
                        TranscodeOutput(
                            url= f"https://freeuuu.obs.cn-east-3.myhuaweicloud.com/{url}",
                            duration=getattr(output_file, "duration", None),
                            size=getattr(output_file, "size", None)*1024,
                            width=getattr(video_meta, "width", None),
                            height=getattr(video_meta, "height", None),
                            video_meta=video_meta,
                            audio_meta=audio_meta
                        )
                    )
                return outputs
            elif status in ["FAILED", "CANCELED"]:
                raise RuntimeError(f"Task {task_id} 执行失败，状态: {status}")
            else:
                # 任务仍在进行中
                elapsed = time.time() - start_time
                if elapsed > timeout:
                    raise TimeoutError(f"Task {task_id} 超时")
                await asyncio.sleep(poll_interval)


# -------------------------------
# 使用示例
# -------------------------------
if __name__ == "__main__":
    client = HuaweiMPCClient()


