from typing import List, Dict, Any, Optional
import uuid

from models.pydantic_models.request.mixed_video_request import MixedVideoRequest
from models.pydantic_models.response.frontend_timeline_response import (
    FrontendTimelineResponse, MetaData, SettingsData, ExportSettings,
    TimelineData, SceneData, VideoClipData, TextTrackData, TextClipData,
    TimeData, SourceData, EffectData, ExtraData, TextContentData,
    SpritesData, VoiceOverData, AudioTrackData, AudioClipData, AudioSourceData, AudioEffectData
)

def build_frontend_timeline(
    req: MixedVideoRequest, 
    fps_list: Optional[List[int]] = None,
    sprites_list: Optional[List[SpritesData]] = None,
    project_id: str = "", 
    project_name: str = "AI生成混剪"
) -> FrontendTimelineResponse:
    if not project_id:
        project_id = str(uuid.uuid4().int >> 64)

    fps = req.fps
    
    try:
        from config.config import get_settings
        pbase = get_settings().pbase
        if not pbase.endswith('/'):
            pbase += '/'
    except Exception:
        pbase = "https://freeuuu.obs.cn-east-3.myhuaweicloud.com/"
        
    def _add_domain(path: str) -> str:
        if not path:
            return path
        if path.startswith("http"):
            return path
        return f"{pbase}{path}"

    # 1. 基础设置与外层包裹
    settings = SettingsData(
        width=1920,
        height=1080,
        fps=fps,
        backgroundColor="#000000"
    )
    
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

    text_track_id = str(uuid.uuid4())
    timeline_data.textTracks.append( TextTrackData(
        id=text_track_id, name="AI_Subtitle_Track", order=1
    ))
    
    audio_track_id = str(uuid.uuid4())
    timeline_data.audioTracks.append( AudioTrackData(
        id=audio_track_id, name="BGM_Track", order=1
    ))

    num_clips = len(req.obs_video_path_list) if req.obs_video_path_list else 0
    current_offset_frames = 0

    scene_starts_in_seconds = []

    for i in range(num_clips):
        scene_id = str(uuid.uuid4())
        
        crop = req.crop_config[i] if req.crop_config and i < len(req.crop_config) else None
        
        current_fps = fps_list[i] if fps_list and i < len(fps_list) else fps
        
        if crop:
            in_point_frames = int(crop.start * current_fps)
            out_point_frames = int(crop.end * current_fps)
        else:
            in_point_frames = 0
            out_point_frames = int(3.0 * current_fps)
            
        length_frames = out_point_frames - in_point_frames

        scene = SceneData(
            id=scene_id,
            order=i + 1,
            name=f"分镜{i+1}",
            duration=length_frames,
            fps=current_fps,
            width=settings.width,
            height=settings.height
        )
        timeline_data.scenes.append(scene)

        # 记录分镜开始的秒数，便于后续字幕分配
        duration_in_seconds = length_frames / current_fps if current_fps else 0
        scene_starts_in_seconds.append({
            "id": scene_id,
            "start": current_offset_frames,
            "duration": duration_in_seconds,
            "fps": current_fps
        })
        current_offset_frames += duration_in_seconds

        sprites = sprites_list[i] if sprites_list and i < len(sprites_list) else None
        if sprites and sprites.sheets:
            for sheet in sprites.sheets:
                sheet.url = _add_domain(sheet.url)

        real_duration = length_frames * 2 # 兜底值
        if sprites and sprites.sheets and len(sprites.sheets) > 0:
            real_duration = sum(s.frameCount for s in sprites.sheets)
            
        material_id = str(uuid.uuid4())

        video_clip = VideoClipData(
            id=str(uuid.uuid4()),
            sceneId=scene_id,
            time=TimeData(
                offset=0,
                length=length_frames,
                inPoint=in_point_frames,
                outPoint=out_point_frames,
                layer=0,
                realDuration=real_duration
            ),
            source=SourceData(
                name=material_id,
                url=_add_domain(req.obs_video_path_list[i]),
                cover=None,
                frames=real_duration,
                width=settings.width,
                height=settings.height,
                materialId=material_id,
                sprites=sprites
            ),
            effect=EffectData(
                muted=req.mute_config[i] if req.mute_config and i < len(req.mute_config) else False
            )
        )
        timeline_data.videoClips.append(video_clip)

    if req.cap_config and req.cap_config.caption_list:
        audio_paths = req.obs_audio_path_list or []
        for cap_idx, cap in enumerate(req.cap_config.caption_list):
            
            # 定位字幕属于哪个分镜
            target_scene_id = timeline_data.scenes[0].id if timeline_data.scenes else str(uuid.uuid4())
            target_fps = fps
            scene_local_offset_seconds = cap.start
            
            accumulated_seconds = 0
            for s_info in scene_starts_in_seconds:
                if accumulated_seconds <= cap.start < (accumulated_seconds + s_info["duration"]):
                    target_scene_id = s_info["id"]
                    target_fps = s_info["fps"]
                    scene_local_offset_seconds = cap.start - accumulated_seconds
                    break
                accumulated_seconds += s_info["duration"]

            cap_in_frames = int(scene_local_offset_seconds * target_fps)
            cap_len_frames = int((cap.end - cap.start) * target_fps)

            voiceover = None
            if cap_idx < len(audio_paths):
                voiceover = VoiceOverData(
                    voiceId="小仙(亲切女声)",
                    speed=1.0,
                    volume=100,
                    audioUrl=_add_domain(audio_paths[cap_idx])
                )

            text_clip = TextClipData(
                id=str(uuid.uuid4()),
                trackId=text_track_id,
                sceneId=target_scene_id,
                time={
                    "offset": cap_in_frames,
                    "length": cap_len_frames
                },
                content=TextContentData(text=cap.cap),
                voiceover=voiceover
            )
            text_clip.style.fontColor.r = 255
            text_clip.style.fontSize = cap.font_size if cap.font_size else req.cap_config.font_size
            
            timeline_data.textClips.append(text_clip)

    if req.bgm_config and req.obs_bgm_path_list:
        for idx, bgm in enumerate(req.bgm_config):
            if idx < len(req.obs_bgm_path_list):
                bgm_url = _add_domain(req.obs_bgm_path_list[idx])
                
                # BGM 是全局的，不依赖于某个特定 scene
                # 将时间 (秒) 转换为全局的帧数
                in_point_frames = int(bgm.start * fps)
                out_point_frames = int(bgm.end * fps)
                length_frames = out_point_frames - in_point_frames
                offset_frames = int(bgm.offset * fps) if hasattr(bgm, 'offset') else 0
                
                audio_clip = AudioClipData(
                    id=str(uuid.uuid4()),
                    trackId=audio_track_id,
                    sceneId=None,
                    time=TimeData(
                        offset=offset_frames,
                        length=length_frames,
                        inPoint=in_point_frames,
                        outPoint=out_point_frames,
                        layer=0,
                        realDuration=length_frames * 2
                    ),
                    source=AudioSourceData(
                        name=f"bgm_{idx}",
                        url=bgm_url,
                        frames=length_frames * 2
                    ),
                    effect=AudioEffectData(
                        volume=int(bgm.volume * 100) if hasattr(bgm, 'volume') else 100,
                        speed=1.0
                    )
                )
                timeline_data.audioClips.append(audio_clip)

    return FrontendTimelineResponse(
        meta=meta,
        settings=settings,
        data=timeline_data
    )
