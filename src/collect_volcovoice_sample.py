import asyncio
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from sqlalchemy import select
from sqlmodel import SQLModel

from database.mysql.mysql_manager import db_manager
from models.pydantic_models.db.volcovoice_sample import VolcovoiceSample
from models.pydantic_models.request.volcovoice_request import Volcovoice_VO, character_options
from models.voice_enums import get_volcano_voice_type
from service.volcovoice_service import process_volcovoice_task
from utils.file_utils import download_file_from_url
from utils.log_utils import logger as log
from utils.obs_utils import upload_audio

DEFAULT_VOLCOVOICE_SAMPLE_TEXT = (
    "你好，欢迎来到智柚引擎。我将为你朗读输入的文本内容，你可以根据自己的创作场景选择最适合的声音。"
)
DEFAULT_VOLCOVOICE_SAMPLE_DIR = Path(__file__).resolve().parent.parent / "volcovoice_sample"
DEFAULT_VOLCOVOICE_SAMPLE_PROJECT_ID = "volcovoice_sample"
DEFAULT_VOLCOVOICE_SAMPLE_CONCURRENCY = 5
DEFAULT_VOLCOVOICE_ERROR_LOG = "volcovoice_sample_errors.txt"


def _safe_filename(name: str) -> str:
    invalid_chars = '<>:"/\\|?*'
    translated = "".join("_" if ch in invalid_chars else ch for ch in name)
    translated = translated.strip().rstrip(".")
    return translated or "voice_sample"


def _infer_extension(url: str) -> str:
    suffix = Path(urlparse(url).path).suffix
    return suffix or ".wav"


def _text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


async def _ensure_sample_table() -> None:
    import models.pydantic_models.db.mix_time_records  # noqa: F401
    import models.pydantic_models.db.volcovoice_sample  # noqa: F401

    async with db_manager.main_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)


async def _load_existing_samples(voice_names: list[str], txt_content: str) -> dict[str, VolcovoiceSample]:
    if not voice_names:
        return {}
    txt_hash = _text_hash(txt_content)
    async with db_manager.SessionLocal() as session:
        stmt = select(VolcovoiceSample).where(
            VolcovoiceSample.txt_hash == txt_hash,
            VolcovoiceSample.voice_character.in_(voice_names),
        )
        result = await session.execute(stmt)
        records = result.scalars().all()
    return {record.voice_character: record for record in records}


async def _upsert_sample_record(
    *,
    voice_character: str,
    voice_type: str | None,
    voice_model_type: str | None,
    voice_code: str,
    txt_content: str,
    local_file_path: str,
    full_voice: str,
    response_json: str,
    debug_json_url: str | None,
) -> VolcovoiceSample:
    txt_hash = _text_hash(txt_content)
    async with db_manager.SessionLocal() as session:
        stmt = select(VolcovoiceSample).where(
            VolcovoiceSample.voice_character == voice_character,
            VolcovoiceSample.txt_hash == txt_hash,
        )
        result = await session.execute(stmt)
        record = result.scalar_one_or_none()
        if record is None:
            record = VolcovoiceSample(
                voice_character=voice_character,
                voice_type=voice_type,
                voice_model_type=voice_model_type,
                voice_code=voice_code,
                txt_content=txt_content,
                txt_hash=txt_hash,
            )
        record.local_file_path = local_file_path
        record.voice_type = voice_type
        record.voice_model_type = voice_model_type
        record.full_voice = full_voice
        record.response_json = response_json
        record.debug_json_url = debug_json_url
        record.txt_content = txt_content
        record.txt_hash = txt_hash
        record.updated_at = datetime.now()
        session.add(record)
        await session.commit()
        await session.refresh(record)
        return record


async def _process_single_voice_sample(
    *,
    voice_character: str,
    voice_code: str,
    txt_content: str,
    output_dir: Path,
) -> dict[str, Any]:
    voice_model_type = get_volcano_voice_type(voice_character)
    voice_type = voice_model_type
    request = Volcovoice_VO(
        biz_id=0,
        user_id=0,
        txt_str=[txt_content],
        voice_character=voice_character,
        audio_speed_level=0,
        volume=80,
    )
    response = await process_volcovoice_task(request)
    if not response.object_list:
        raise RuntimeError(f"volcovoice returned empty object_list for {voice_character}")

    response_payload = response.model_dump()
    response_json = json.dumps(response_payload, ensure_ascii=False, indent=2)
    first_object = response.object_list[0]
    full_voice_url = first_object.full_voice
    local_ext = _infer_extension(full_voice_url)
    local_file_path = output_dir / f"{_safe_filename(voice_character)}{local_ext}"
    local_json_path = output_dir / f"{_safe_filename(voice_character)}.json"

    await asyncio.to_thread(download_file_from_url, full_voice_url, str(local_file_path))
    await asyncio.to_thread(local_json_path.write_text, response_json, "utf-8")
    uploaded_sample_url = await upload_audio(str(local_file_path), project_id=DEFAULT_VOLCOVOICE_SAMPLE_PROJECT_ID)

    record = await _upsert_sample_record(
        voice_character=voice_character,
        voice_type=voice_type,
        voice_model_type=voice_model_type,
        voice_code=voice_code,
        txt_content=txt_content,
        local_file_path=str(local_file_path),
        full_voice=uploaded_sample_url,
        response_json=response_json,
        debug_json_url=response.debug_json_url,
    )

    return {
        "voice_character": voice_character,
        "voice_type": voice_type,
        "voice_model_type": voice_model_type,
        "voice_code": voice_code,
        "status": "sampled",
        "local_file_path": str(local_file_path),
        "full_voice": uploaded_sample_url,
        "duration": first_object.duration,
        "detail_count": len(first_object.detail_info),
        "record_id": record.id,
        "debug_json_url": response.debug_json_url,
    }


def _append_error_log(
    error_log_path: Path,
    *,
    voice_character: str,
    voice_type: str,
    voice_model_type: str,
    voice_code: str,
    txt_content: str,
    error: Exception,
) -> None:
    timestamp = datetime.now().isoformat(timespec="seconds")
    error_type = type(error).__name__
    error_message = str(error).replace("\n", " ").strip()
    line = (
        f"[{timestamp}] voice_character={voice_character} | voice_type={voice_type} | voice_model_type={voice_model_type} | voice_code={voice_code} | "
        f"error_type={error_type} | error_message={error_message} | text={txt_content}\n"
    )
    error_log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(error_log_path, "a", encoding="utf-8") as f:
        f.write(line)


async def sample_volcovoice_voices(
    *,
    k: int,
    resample: bool = False,
    txt_content: str = DEFAULT_VOLCOVOICE_SAMPLE_TEXT,
    concurrency: int = DEFAULT_VOLCOVOICE_SAMPLE_CONCURRENCY,
    output_dir: Path | None = None,
) -> dict[str, Any]:
    await _ensure_sample_table()

    sample_dir = output_dir or DEFAULT_VOLCOVOICE_SAMPLE_DIR
    sample_dir.mkdir(parents=True, exist_ok=True)
    error_log_path = sample_dir / DEFAULT_VOLCOVOICE_ERROR_LOG

    voice_items = list(character_options.items())[: max(0, k)]
    voice_names = [display_name for display_name, _ in voice_items]
    existing_map = await _load_existing_samples(voice_names, txt_content)

    sem = asyncio.Semaphore(max(1, concurrency))

    async def _worker(display_name: str, voice_code: str) -> dict[str, Any]:
        voice_model_type = get_volcano_voice_type(display_name)
        voice_type = voice_model_type
        if not resample and display_name in existing_map:
            record = existing_map[display_name]
            return {
                "voice_character": display_name,
                "voice_type": record.voice_type or voice_type,
                "voice_model_type": record.voice_model_type or voice_model_type,
                "voice_code": voice_code,
                "status": "skipped",
                "local_file_path": record.local_file_path,
                "full_voice": record.full_voice,
                "record_id": record.id,
                "debug_json_url": record.debug_json_url,
            }

        async with sem:
            try:
                return await _process_single_voice_sample(
                    voice_character=display_name,
                    voice_code=voice_code,
                    txt_content=txt_content,
                    output_dir=sample_dir,
                )
            except Exception as exc:
                await asyncio.to_thread(
                    _append_error_log,
                    error_log_path,
                    voice_character=display_name,
                    voice_type=voice_type,
                    voice_model_type=voice_model_type,
                    voice_code=voice_code,
                    txt_content=txt_content,
                    error=exc,
                )
                log.exception(f"Volcovoice sample failed for {display_name} ({voice_code})")
                return {
                    "voice_character": display_name,
                    "voice_type": voice_type,
                    "voice_model_type": voice_model_type,
                    "voice_code": voice_code,
                    "status": "failed",
                    "error_type": type(exc).__name__,
                    "error_message": str(exc),
                    "error_log_path": str(error_log_path),
                }

    results = await asyncio.gather(*[_worker(display_name, voice_code) for display_name, voice_code in voice_items])
    sampled_count = sum(1 for item in results if item["status"] == "sampled")
    skipped_count = sum(1 for item in results if item["status"] == "skipped")
    failed_count = sum(1 for item in results if item["status"] == "failed")

    summary = {
        "txt_content": txt_content,
        "k": len(voice_items),
        "resample": resample,
        "concurrency": max(1, concurrency),
        "output_dir": str(sample_dir),
        "sampled_count": sampled_count,
        "skipped_count": skipped_count,
        "failed_count": failed_count,
        "error_log_path": str(error_log_path),
        "results": results,
    }

    summary_path = sample_dir / "volcovoice_sample_summary.json"
    await asyncio.to_thread(summary_path.write_text, json.dumps(summary, ensure_ascii=False, indent=2), "utf-8")
    log.info(f"Volcovoice sample summary written to {summary_path}")
    return summary
