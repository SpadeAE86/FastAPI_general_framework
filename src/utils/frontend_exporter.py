import math
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
    SpriteSheet,
    TextClipData,
    TextContentData,
    TextTrackData,
    TimeData,
    VideoClipData,
    VoiceOverData,
    TimelineData,
)


DEFAULT_VOICE_ID = "小仙(亲切女声)"


def _build_voiceover(audio_info: Optional[FrontendAudioInfo], audio_url: str) -> dict:
    audio_info = audio_info or FrontendAudioInfo()
    speed = 2 ** (audio_info.audio_speed_level / 500) if audio_info.audio_speed_level else 1.0
    return VoiceOverData(
        voiceId=audio_info.voice_character or DEFAULT_VOICE_ID,
        speed=speed,
        volume=audio_info.volume,
        audioUrl=audio_url,
    ).model_dump(exclude_none=True)


def _normalize_audio_infos(audio_info_list: Optional[List[FrontendAudioInfo]], caption_count: int) -> List[FrontendAudioInfo]:
    if not audio_info_list:
        return [FrontendAudioInfo() for _ in range(caption_count)]
    normalized: List[FrontendAudioInfo] = []
    for item in audio_info_list:
        if isinstance(item, FrontendAudioInfo):
            normalized.append(item)
        else:
            normalized.append(FrontendAudioInfo(**item))
    if len(normalized) < caption_count:
        normalized.extend(FrontendAudioInfo() for _ in range(caption_count - len(normalized)))
    return normalized


def _normalize_video_infos(video_info_list: Optional[List[FrontendVideoInfo]]) -> List[FrontendVideoInfo]:
    if not video_info_list:
        return []
    return [
        item if isinstance(item, FrontendVideoInfo) else FrontendVideoInfo(**item)
        for item in video_info_list
    ]


def _infer_source_frames(video_info: FrontendVideoInfo, current_fps: int, fallback_frames: int) -> int:
    """
    Prefer explicit source metadata, then duration-based inference, then sprite metadata.

    The frontend expects `source.frames` and `time.realDuration` to describe the original
    material frame count, not the sampled sprite-sheet count.
    """
    if video_info.source_frames and video_info.source_frames > 0:
        return int(video_info.source_frames)

    if video_info.duration and current_fps:
        return int(round(video_info.duration * current_fps))

    if video_info.sprites:
        sample_interval = video_info.sprites.sampleInterval or video_info.sprite_sample_interval or 5
        total_samples = video_info.sprites.totalSamples
        if not total_samples:
            total_samples = sum((sheet.frameCount or 0) for sheet in video_info.sprites.sheets)
        if total_samples > 0:
            return int(total_samples * sample_interval)

    return int(fallback_frames)


def _normalize_sprites(
    video_info: FrontendVideoInfo,
    source_frames: int,
    add_domain,
) -> Optional[SpritesData]:
    if not video_info.sprites:
        return None

    sprites = video_info.sprites.model_copy(deep=True)
    sample_interval = sprites.sampleInterval or video_info.sprite_sample_interval or 5
    frame_width = sprites.frameWidth or video_info.sprite_frame_width or 200
    frame_height = sprites.frameHeight or video_info.sprite_frame_height or 112
    default_cols = video_info.sprite_cols or 12
    default_rows = video_info.sprite_rows or 20

    sprites.sampleInterval = sample_interval
    sprites.frameWidth = frame_width
    sprites.frameHeight = frame_height

    total_samples = sprites.totalSamples or 0
    if total_samples <= 0 and source_frames > 0:
        total_samples = int(math.ceil(source_frames / sample_interval))
    if total_samples <= 0 and sprites.sheets:
        total_samples = sum((sheet.frameCount or 0) for sheet in sprites.sheets)

    normalized_sheets: List[SpriteSheet] = []
    next_start_frame = 0
    for idx, sheet in enumerate(sprites.sheets):
        cols = sheet.cols or default_cols
        rows = sheet.rows or default_rows
        frames_per_sheet = cols * rows
        # Normalize startFrame in the sampled-frame space, not raw video-frame space.
        # The first sheet starts at 0, and each later sheet starts where the previous one ended.
        start_frame = next_start_frame
        if sheet.startFrame not in (None, 0) and sheet.startFrame != start_frame:
            start_frame = sheet.startFrame

        if total_samples > 0:
            remaining_samples = max(total_samples - start_frame, 0)
            frame_count = min(frames_per_sheet, remaining_samples)
        else:
            frame_count = sheet.frameCount or frames_per_sheet

        normalized_sheets.append(
            SpriteSheet(
                url=add_domain(sheet.url),
                cols=cols,
                rows=rows,
                frameCount=frame_count,
                startFrame=start_frame,
            )
        )

        next_start_frame = start_frame + frame_count

    sprites.sheets = normalized_sheets
    if total_samples > 0:
        sprites.totalSamples = total_samples
    return sprites


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
    selected_by_scene: List[List[str]] = []

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

        video_info = normalized_video_infos[i] if i < len(normalized_video_infos) else FrontendVideoInfo()
        current_fps = video_info.fps if video_info.fps else fps

        if crop:
            in_point_frames = int(crop.start * current_fps)
            out_point_frames = int(crop.end * current_fps)
        else:
            in_point_frames = 0
            out_point_frames = int(3.0 * current_fps)

        length_frames = out_point_frames - in_point_frames
        fallback_source_frames = length_frames * 2
        source_frames = _infer_source_frames(video_info, current_fps, fallback_source_frames)
        sprites = _normalize_sprites(video_info, source_frames, _add_domain)
        source_width = video_info.width or settings.width
        source_height = video_info.height or settings.height
        material_id = video_info.material_id or str(uuid.uuid4())

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

        # `realDuration` and `source.frames` track the original material frame count.
        video_clip = VideoClipData(
            id=str(uuid.uuid4()),
            sceneId=scene_id,
            time=TimeData(
                offset=0,
                length=length_frames,
                inPoint=in_point_frames,
                outPoint=out_point_frames,
                layer=0,
                realDuration=source_frames,
            ),
            source=SourceData(
                name=material_id,
                url=_add_domain(req.obs_video_path_list[i]),
                cover=_add_domain(video_info.source_cover) if video_info.source_cover else None,
                frames=source_frames,
                width=source_width,
                height=source_height,
                materialId=material_id,
                sprites=sprites,
            ),
            effect=EffectData(
                muted=req.mute_config[i] if req.mute_config and i < len(req.mute_config) else False
            ),
        )
        timeline_data.videoClips.append(video_clip)
        selected_by_scene.append([video_clip.id])

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

            audio_info = normalized_audio_infos[cap_idx] if cap_idx < len(normalized_audio_infos) else FrontendAudioInfo()
            audio_url = audio_info.audio_url or (audio_paths[cap_idx] if cap_idx < len(audio_paths) else "")
            voiceover = _build_voiceover(audio_info, _add_domain(audio_url)) if audio_url else {}

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

    timeline_data.selection.selectedByScene = selected_by_scene

    return FrontendTimelineResponse(
        meta=meta,
        settings=settings,
        data=timeline_data,
    )
