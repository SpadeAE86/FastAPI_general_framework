from typing import List, Dict, Any
import uuid

from models.pydantic_models.request.mixed_video_request import MixedVideoRequest
from models.pydantic_models.response.frontend_timeline_response import (
    FrontendTimelineResponse, MetaData, SettingsData, ExportSettings,
    TimelineData, SceneData, VideoClipData, TextTrackData, TextClipData,
    TimeData, SourceData, EffectData, ExtraData, TextContentData
)

def build_frontend_timeline(req: MixedVideoRequest, project_id: str = "", project_name: str = "AI生成混剪") -> FrontendTimelineResponse:
    """
    将后端的 MixedVideoRequest 转换为前端可视化的 Timeline JSON。
    前提：前端在发起请求时，需要在 req.request_data 里或者额外字段里传入被选中的视频的物料元数据(帧数、雪碧图等)。
    如果缺这些数据，这里将使用简单的推导或默认值兜底。
    """
    if not project_id:
        project_id = str(uuid.uuid4().int >> 64)

    fps = req.fps
    
    # 1. 基础设置与外层包裹
    settings = SettingsData(
        width=1920, # 默认值，可以根据 req.resolution 去映射字典
        height=1080,
        fps=fps,
        backgroundColor="#000000"
    )
    
    # 尝试从 resolution 里匹配真正的宽高（如果后端有枚举解析逻辑最好）
    if req.resolution and req.ratio_type:
        from models.pydantic_models.request.mixed_video_request import ratio_option
        if req.resolution in ratio_option and req.ratio_type in ratio_option[req.resolution]:
            w, h = ratio_option[req.resolution][req.ratio_type]
            settings.width = w
            settings.height = h

    meta = MetaData(
        id=project_id,
        name=project_name,
        createdAt=0,
        updatedAt=0
    )

    timeline_data = TimelineData()

    # 创建一条统一的视频轨（其实在前端 JSON 里，video 不用显式声明 track，直接放在 videoClips 即可）
    # 创建一条唯一的文字轨
    text_track_id = str(uuid.uuid4())
    timeline_data.textTracks.append( TextTrackData(
        id=text_track_id, name="AI_Subtitle_Track", order=1
    ))

    # 2. 遍历片段生成 Scene, VideoClip, TextClip
    # 因为用户说：每个分镜里就只剩一条视频clip和文本clip
    num_clips = len(req.obs_video_path_list)
    
    # 获取外部传入的元数据 (如果是存在 request_data 里面)
    # 假设 request_data 是个字典，里面有 `video_metas: [{frames, sprites, materialId}, ...]`
    # 这里做个安全兜底，假装没传的话就用推导
    raw_metas = getattr(req, "request_data", {}) or {}
    video_metas = raw_metas.get("video_metas", [])

    current_offset_frames = 0

    for i in range(num_clips):
        scene_id = str(uuid.uuid4())
        
        # --- 算时间 ---
        # 视频裁剪 config
        crop = req.crop_config[i] if req.crop_config and i < len(req.crop_config) else None
        
        if crop:
            in_point_frames = int(crop.start * fps)
            out_point_frames = int(crop.end * fps)
        else:
            in_point_frames = 0
            # 没传裁剪的话给个默认3秒
            out_point_frames = int(3.0 * fps)
            
        length_frames = out_point_frames - in_point_frames

        # --- Scene ---
        scene = SceneData(
            id=scene_id,
            order=i + 1,
            name=f"分镜{i+1}",
            duration=length_frames,
            fps=fps,
            width=settings.width,
            height=settings.height
        )
        timeline_data.scenes.append(scene)

        # --- 获取外部元数据（提取帧数字典） ---
        meta_dict = video_metas[i] if i < len(video_metas) else {}
        real_duration = meta_dict.get("frames", length_frames * 2) # 没有就瞎猜比裁剪长一倍
        material_id = meta_dict.get("materialId", str(uuid.uuid4()))
        sprites = meta_dict.get("sprites", None)

        # --- VideoClip ---
        video_clip = VideoClipData(
            id=str(uuid.uuid4()),
            sceneId=scene_id,
            time=TimeData(
                offset=0, # 注意：由于每个Clip独占一个Scene，所以在Scene内部它的offset通常为0！
                length=length_frames,
                inPoint=in_point_frames,
                outPoint=out_point_frames,
                layer=0,
                realDuration=real_duration
            ),
            source=SourceData(
                name=material_id,
                url=req.obs_video_path_list[i],
                cover=None,
                frames=real_duration,
                width=settings.width,  # 这里最好填原视频的宽
                height=settings.height,
                materialId=material_id,
                sprites=sprites
            ),
            effect=EffectData(
                muted=req.mute_config[i] if req.mute_config and i < len(req.mute_config) else False
            )
        )
        timeline_data.videoClips.append(video_clip)

        # 往前累加全局 Timeline 游标（给外部计算总长度参考用的，虽然 scene 内部 offset 为 0）
        current_offset_frames += length_frames

    # --- 3. TextClips 字幕 ---
    if req.cap_config and req.cap_config.caption_list:
        # 字幕是全局覆盖在整个 Timeline 上的，通常不严格挂载在 Scene 内（或者挂在一个特殊的 Global Scene 里）
        # 如果你们前端格式要求 TextClip 必须有个属主 sceneId，那我们就把所有字幕按时间切到对应的 Scene 进去
        
        for cap_idx, cap in enumerate(req.cap_config.caption_list):
            cap_in_frames = int(cap.start * fps)
            cap_out_frames = int(cap.end * fps)
            cap_len_frames = cap_out_frames - cap_in_frames
            
            # 为了严谨，需要根据 cap_in_frames 处于哪个 Scene，把字幕绑定过去
            # 这里简单起见，把它挂靠到第一个 Scene 或通过累计时间算它落在哪个 Scene
            # 这是一个典型的 NLE 倒推逻辑：
            accumulated = 0
            target_scene_id = timeline_data.scenes[0].id
            scene_local_offset = cap_in_frames
            
            for s in timeline_data.scenes:
                if accumulated <= cap_in_frames < (accumulated + s.duration):
                    target_scene_id = s.id
                    scene_local_offset = cap_in_frames - accumulated
                    break
                accumulated += s.duration

            text_clip = TextClipData(
                id=str(uuid.uuid4()),
                trackId=text_track_id,
                sceneId=target_scene_id,
                time={
                    "offset": scene_local_offset,
                    "length": cap_len_frames
                },
                content=TextContentData(text=cap.cap)
            )
            # 字体样式
            text_clip.style.fontColor.r = 255
            text_clip.style.fontSize = cap.font_size if cap.font_size else req.cap_config.font_size
            
            # 还可以填 voiceover 语音
            
            timeline_data.textClips.append(text_clip)

    return FrontendTimelineResponse(
        meta=meta,
        settings=settings,
        data=timeline_data
    )
