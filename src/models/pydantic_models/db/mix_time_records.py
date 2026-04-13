from datetime import datetime
from typing import Optional
from sqlmodel import SQLModel, Field
from sqlalchemy import Column, Text

class MixVideoOverallTime(SQLModel, table=True):
    __tablename__ = "mix_video_overall_time"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    biz_id: str = Field(index=True, max_length=128, description="业务ID")
    status: str = Field(default="received", max_length=32, description="处理状态：received, started, done, failed")
    
    start_time: Optional[datetime] = Field(default=None, description="任务(服务层)开始时间")
    task_received_at: Optional[datetime] = Field(default=None, description="原始任务被网关接收的时间(如果有)")
    end_time: Optional[datetime] = Field(default=None, description="任务结束时间")
    
    cost_time: Optional[float] = Field(default=None, description="总耗时(秒)")
    download_cost: Optional[float] = Field(default=None, description="下载素材耗时(秒)")
    cap_gen_cost: Optional[float] = Field(default=None, description="生成字幕图片耗时(秒)")
    normalize_cost: Optional[float] = Field(default=None, description="分镜预处理并发耗时(秒)")
    concat_cost: Optional[float] = Field(default=None, description="音视频合成组装耗时(秒)")
    upload_cost: Optional[float] = Field(default=None, description="结果推流上传耗时(秒)")
    
    request_data: Optional[str] = Field(default=None, sa_column=Column(Text), description="JSON格式的请求体数据")
    output_url: Optional[str] = Field(default=None, sa_column=Column(Text), description="生成的混剪视频地址")
    cover_url: Optional[str] = Field(default=None, sa_column=Column(Text), description="封面图片地址")
    error_msg: Optional[str] = Field(default=None, sa_column=Column(Text), description="运行期间报错信息(若失败)")


class MixVideoSceneTime(SQLModel, table=True):
    __tablename__ = "mix_video_scene_time"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    biz_id: str = Field(index=True, max_length=128, description="所属的业务ID")
    scene_idx: int = Field(description="分镜序号")
    cost_time: float = Field(description="该分镜处理耗时(秒)")
    
    created_at: datetime = Field(default_factory=datetime.now)
