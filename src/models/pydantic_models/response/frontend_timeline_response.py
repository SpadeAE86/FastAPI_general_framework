from pydantic import BaseModel, Field
from typing import List, Optional, Any, Dict

from .base_response import BaseResponse

class MetaData(BaseModel):
    id: str = Field(description="项目ID")
    name: str = Field(description="项目名称")
    createdAt: int = Field(description="创建时间戳")
    updatedAt: int = Field(description="更新时间戳")

class SettingsData(BaseModel):
    width: int = Field(description="画布宽度")
    height: int = Field(description="画布高度")
    fps: int = Field(description="帧率")
    backgroundColor: str = Field(default="#000000", description="背景颜色")

class ExportSettings(BaseModel):
    format: str = Field(default="mp4")
    codec: str = Field(default="h264")
    quality: int = Field(default=80)
    scale: int = Field(default=1)

class SceneData(BaseModel):
    id: str = Field(description="场景唯一标识")
    order: int = Field(description="场景序号")
    name: str = Field(default="分镜", description="场景名称")
    duration: int = Field(description="场景长度（帧数）")
    fps: int = Field(description="场景帧率")
    width: int = Field(description="场景宽度")
    height: int = Field(description="场景高度")

class TimeData(BaseModel):
    offset: int = Field(description="该片段在当前场景时间线上的起始帧")
    length: int = Field(description="该片段在时间线上占据的帧数")
    inPoint: int = Field(description="片头裁剪帧")
    outPoint: int = Field(description="片尾裁剪帧")
    layer: Optional[int] = Field(default=0, description="图层层级（Z-index）")
    realDuration: Optional[int] = Field(default=None, description="原视频总帧数")

class SpriteSheet(BaseModel):
    url: str
    cols: int = Field(default=12)
    rows: int = Field(default=20)
    frameCount: int
    startFrame: int = Field(default=0)

class SpritesData(BaseModel):
    sheets: List[SpriteSheet] = Field(default_factory=list)
    sampleInterval: int = Field(default=5)
    totalSamples: int = Field(default=0)
    frameWidth: int = Field(default=200)
    frameHeight: int = Field(default=112)

class SourceData(BaseModel):
    name: str = Field(description="素材名称或ID")
    url: str = Field(description="素材CDN链接")
    cover: Optional[str] = Field(default=None, description="视频封面截图链接")
    frames: Optional[int] = Field(default=None, description="视频本身的总帧长")
    width: Optional[int] = Field(default=None, description="视频原高宽")
    height: Optional[int] = Field(default=None, description="视频原高")
    sprites: Optional[SpritesData] = Field(default=None, description="视频缩略图雪碧图信息")
    materialId: str = Field(description="素材业务ID")

class EffectData(BaseModel):
    speed: float = Field(default=1)
    volume: int = Field(default=100)
    muted: bool = Field(default=False)
    mirrored: bool = Field(default=False)
    filters: List[Any] = Field(default_factory=list)
    scale: int = Field(default=100)
    positionX: float = Field(default=0)
    positionY: float = Field(default=0)
    rotation: float = Field(default=0)
    temperature: float = Field(default=0)
    tint: float = Field(default=0)
    saturation: float = Field(default=1)

class ExtraData(BaseModel):
    dragId: Optional[str] = None
    isLoading: bool = Field(default=False)

class VideoClipData(BaseModel):
    id: str = Field(description="轨道片段ID")
    sceneId: str = Field(description="所属场景ID")
    time: TimeData = Field(description="时间裁剪与位置信息")
    source: SourceData = Field(description="视频源信息")
    effect: EffectData = Field(default_factory=EffectData, description="滤镜和特效配置")
    extra: ExtraData = Field(default_factory=ExtraData, description="UI额外字段")

class TextTrackData(BaseModel):
    id: str
    name: str
    order: int
    visible: bool = Field(default=True)
    locked: bool = Field(default=False)

class FontColorData(BaseModel):
    r: int = 255
    g: int = 255
    b: int = 255
    a: float = 1.0

class TextStyleData(BaseModel):
    fontFamily: str = Field(default='"Songti SC", "STSong", "SimSun", "宋体"')
    fontSize: int = Field(default=24)
    fontColor: FontColorData = Field(default_factory=FontColorData)
    bold: bool = Field(default=False)
    italic: bool = Field(default=False)

class TextPositionData(BaseModel):
    x: float = Field(default=0)
    y: float = Field(default=0.8)
    align: str = Field(default="center")

class TextContentData(BaseModel):
    text: str

class VoiceOverData(BaseModel):
    voiceId: str
    speed: float = Field(default=1.0)
    volume: int = Field(default=100)
    audioUrl: str

class TextClipData(BaseModel):
    id: str
    trackId: str
    sceneId: str
    time: Dict[str, Any] = Field(description="只包含 offset 和 length 的字典")
    content: TextContentData
    style: TextStyleData = Field(default_factory=TextStyleData)
    position: TextPositionData = Field(default_factory=TextPositionData)
    voiceover: Optional[VoiceOverData] = Field(default=None)

class AudioTrackData(BaseModel):
    id: str
    name: str
    order: int
    visible: bool = Field(default=True)
    locked: bool = Field(default=False)

class AudioSourceData(BaseModel):
    name: str
    url: str
    frames: Optional[int] = Field(default=None)

class AudioEffectData(BaseModel):
    speed: float = Field(default=1.0)
    volume: int = Field(default=100)
    fadeIn: int = Field(default=0)
    fadeOut: int = Field(default=0)

class AudioClipData(BaseModel):
    id: str
    trackId: str
    sceneId: Optional[str] = Field(default=None)
    time: TimeData
    source: AudioSourceData
    effect: AudioEffectData = Field(default_factory=AudioEffectData)

class SelectionData(BaseModel):
    selectedByScene: List[List[str]] = Field(default_factory=list)
    selectedType: Optional[str] = Field(default=None)
    selectedClipId: Optional[str] = Field(default=None)

class TimelineData(BaseModel):
    scenes: List[SceneData] = Field(default_factory=list)
    videoClips: List[VideoClipData] = Field(default_factory=list)
    textTracks: List[TextTrackData] = Field(default_factory=list)
    textClips: List[TextClipData] = Field(default_factory=list)
    audioTracks: List[AudioTrackData] = Field(default_factory=list)
    audioClips: List[AudioClipData] = Field(default_factory=list)
    splitClips: List[Any] = Field(default_factory=list)
    selection: SelectionData = Field(default_factory=SelectionData)

class FrontendTimelineResponse(BaseResponse):
    """
    专门用来将混剪请求反向生成为前端展示 JSON 用的 Pydantic Response 模型
    继承自 BaseResponse，这样外层可以保持统一格式
    """
    version: str = Field(default="1.0.0", description="版本号")
    meta: MetaData
    settings: SettingsData
    exportSettings: ExportSettings = Field(default_factory=ExportSettings)
    data: TimelineData
