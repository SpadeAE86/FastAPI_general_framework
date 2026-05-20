from typing import List, Optional
import uuid

from models.pydantic_models.request.frontend_timeline_request import FrontendAudioInfo, FrontendVideoInfo
from models.pydantic_models.request.mixed_video_request import MixedVideoRequest
from models.pydantic_models.response.frontend_timeline_response import (
    AudioClipData,
    AudioEffectData,
    AudioSourceData,
    AudioTrackData,
    EffectData,
    FrontendTimelineResponse,
    MetaData,
    SceneData,
    SettingsData,
    SourceData,
    SpritesData,
    TextClipData,
    TextContentData,
    TextTrackData,
    TimeData,
    VideoClipData,
    VoiceOverData,
    TimelineData,
)


DEFAULT_VOICE_ID = "小仙(亲切女声)"


def _build_voiceover(audio_info: Optional[FrontendAudioInfo], audio_url: str) -> VoiceOverData:
    audio_info = audio_info or FrontendAudioInfo()
    speed = 2 ** (audio_info.audio_speed_level / 500) if audio_info.audio_speed_level else 1.0
    return VoiceOverData(
        voiceId=audio_info.voice_character or DEFAULT_VOICE_ID,
        speed=speed,
        volume=audio_info.volume,
        audioUrl=audio_url,
    )


def _normalize_audio_infos(audio_info_list: Optional[List[FrontendAudioInfo]], caption_count: int) -> List[FrontendAudioInfo]:
    if not audio_info_list:
        return [FrontendAudioInfo() for _ in range(caption_count)]
    normalized: List[FrontendAudioInfo] = []
    for item in audio_info_list:
        if isinstance(item, FrontendAudioInfo):
            normalized.append(item)
        else:
            normalized.append(FrontendAudioInfo(**item))
    return normalized


def _normalize_video_infos(video_info_list: Optional[List[FrontendVideoInfo]]) -> List[FrontendVideoInfo]:
    if not video_info_list:
        return []
    return [
        item if isinstance(item, FrontendVideoInfo) else FrontendVideoInfo(**item)
        for item in video_info_list
    ]


def build_frontend_timeline(
    req: MixedVideoRequest,
    video_info_list: Optional[List[FrontendVideoInfo]] = None,
    audio_info_list: Optional[List[FrontendAudioInfo]] = None,
    project_id: str = "",
    project_name: str = "AI生成混剪",
) -> FrontendTimelineResponse:
    if not project_id:
        project_id = str(uuid.uuid4().int >> 64)

    fps = req.fps

    try:
        from config.config import get_settings

        pbase = get_settings().pbase
        if not pbase.endswith("/"):
            pbase += "/"
    except Exception:
        pbase = "https://freeuuu.obs.cn-east-3.myhuaweicloud.com/"

    def _add_domain(path: str) -> str:
        if not path:
            return path
        if path.startswith("http"):
            return path
        return f"{pbase}{path}"

    settings = SettingsData(
        width=1920,
        height=1080,
        fps=fps,
        backgroundColor="#000000",
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
        updatedAt=0,
    )

    timeline_data = TimelineData()

    text_track_id = str(uuid.uuid4())
    timeline_data.textTracks.append(TextTrackData(id=text_track_id, name="AI_Subtitle_Track", order=1))

    audio_track_id = str(uuid.uuid4())
    timeline_data.audioTracks.append(AudioTrackData(id=audio_track_id, name="BGM_Track", order=1))

    num_clips = len(req.obs_video_path_list) if req.obs_video_path_list else 0
    current_offset_frames = 0.0
    scene_starts_in_seconds = []

    normalized_video_infos = _normalize_video_infos(video_info_list)
    if len(normalized_video_infos) < num_clips:
        normalized_video_infos.extend(
            [FrontendVideoInfo() for _ in range(num_clips - len(normalized_video_infos))]
        )

    for i in range(num_clips):
        scene_id = str(uuid.uuid4())
        crop = req.crop_config[i] if req.crop_config and i < len(req.crop_config) else None

        current_fps = normalized_video_infos[i].fps if i < len(normalized_video_infos) and normalized_video_infos[i].fps else fps
        sprites = normalized_video_infos[i].sprites if i < len(normalized_video_infos) else None

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
            name=f"分镜{i + 1}",
            duration=length_frames,
            fps=current_fps,
            width=settings.width,
            height=settings.height,
        )
        timeline_data.scenes.append(scene)

        duration_in_seconds = length_frames / current_fps if current_fps else 0
        scene_starts_in_seconds.append(
            {
                "id": scene_id,
                "start": current_offset_frames,
                "duration": duration_in_seconds,
                "fps": current_fps,
            }
        )
        current_offset_frames += duration_in_seconds

        if sprites and sprites.sheets:
            for sheet in sprites.sheets:
                sheet.url = _add_domain(sheet.url)

        real_duration = length_frames * 2
        if sprites and sprites.sheets:
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
                realDuration=real_duration,
            ),
            source=SourceData(
                name=material_id,
                url=_add_domain(req.obs_video_path_list[i]),
                cover=None,
                frames=real_duration,
                width=settings.width,
                height=settings.height,
                materialId=material_id,
                sprites=sprites,
            ),
            effect=EffectData(
                muted=req.mute_config[i] if req.mute_config and i < len(req.mute_config) else False
            ),
        )
        timeline_data.videoClips.append(video_clip)

    audio_paths = req.obs_audio_path_list or []
    caption_list = req.cap_config.caption_list if req.cap_config and req.cap_config.caption_list else []
    normalized_audio_infos = _normalize_audio_infos(audio_info_list, len(caption_list))

    if caption_list:
        for cap_idx, cap in enumerate(caption_list):
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
                audio_info = normalized_audio_infos[cap_idx] if cap_idx < len(normalized_audio_infos) else FrontendAudioInfo()
                voiceover = _build_voiceover(audio_info, _add_domain(audio_paths[cap_idx]))

            text_clip = TextClipData(
                id=str(uuid.uuid4()),
                trackId=text_track_id,
                sceneId=target_scene_id,
                time={
                    "offset": cap_in_frames,
                    "length": cap_len_frames,
                },
                content=TextContentData(text=cap.cap),
                voiceover=voiceover,
            )
            text_clip.style.fontColor.r = 255
            text_clip.style.fontSize = cap.font_size if cap.font_size else req.cap_config.font_size
            timeline_data.textClips.append(text_clip)

    if req.bgm_config and req.obs_bgm_path_list:
        for idx, bgm in enumerate(req.bgm_config):
            if idx >= len(req.obs_bgm_path_list):
                break
            bgm_url = _add_domain(req.obs_bgm_path_list[idx])
            in_point_frames = int(bgm.start * fps)
            out_point_frames = int(bgm.end * fps)
            length_frames = out_point_frames - in_point_frames
            offset_frames = int(bgm.offset * fps) if hasattr(bgm, "offset") else 0

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
                    realDuration=length_frames * 2,
                ),
                source=AudioSourceData(
                    name=f"bgm_{idx}",
                    url=bgm_url,
                    frames=length_frames * 2,
                ),
                effect=AudioEffectData(
                    volume=int(bgm.volume * 100) if hasattr(bgm, "volume") else 100,
                    speed=1.0,
                ),
            )
            timeline_data.audioClips.append(audio_clip)

    return FrontendTimelineResponse(
        meta=meta,
        settings=settings,
        data=timeline_data,
    )
