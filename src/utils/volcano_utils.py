import base64
import json
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import requests
import websockets

from config.config import my_config
from exceptions.ServiceException import ServiceException
from sdk.volcano_protocols import MsgType, full_client_request, receive_message
from utils.log_utils import logger as log


@dataclass
class VolcanoWordTimestamp:
    word: str
    start_time: float
    end_time: float
    confidence: Optional[float] = None


@dataclass
class VolcanoSentenceTimestamp:
    event: Optional[str]
    text: str
    words: list[VolcanoWordTimestamp] = field(default_factory=list)


@dataclass
class VolcanoTimestampsDebugResult:
    api_generation: str
    timestamp_mode: str
    output_path: str
    audio_bytes: int
    event_count: int
    usage: Optional[dict[str, Any]] = None
    sentences: list[VolcanoSentenceTimestamp] = field(default_factory=list)
    raw_events: list[dict[str, Any]] = field(default_factory=list)


def _normalize_word_timestamp(raw_word: dict[str, Any]) -> VolcanoWordTimestamp:
    return VolcanoWordTimestamp(
        word=str(raw_word.get("word", "")),
        start_time=float(raw_word.get("startTime", raw_word.get("start", 0.0))),
        end_time=float(raw_word.get("endTime", raw_word.get("end", 0.0))),
        confidence=float(raw_word["confidence"]) if raw_word.get("confidence") is not None else None,
    )


def _collect_sentence_from_payload(event_name: Optional[str], payload: dict[str, Any]) -> Optional[VolcanoSentenceTimestamp]:
    sentence = payload.get("sentence")
    if not isinstance(sentence, dict):
        return None

    words = sentence.get("words") or []
    if not words:
        return None

    return VolcanoSentenceTimestamp(
        event=event_name,
        text=str(sentence.get("text", "")),
        words=[_normalize_word_timestamp(word) for word in words if isinstance(word, dict)],
    )


def _get_volcano_v3_headers(volcano_config: dict[str, Any], request_id: str) -> dict[str, str]:
    api_key = volcano_config.get("api_key")
    resource_id = volcano_config.get("resource_id")
    app_id = volcano_config.get("app_id") or volcano_config.get("appid")
    access_token = volcano_config.get("access_token")

    if api_key and resource_id:
        return {
            "X-Api-Key": api_key,
            "X-Api-Resource-Id": resource_id,
            "X-Api-Request-Id": request_id,
            "Content-Type": "application/json",
        }

    if app_id and access_token and resource_id:
        return {
            "X-Api-App-Id": str(app_id),
            "X-Api-Access-Key": access_token,
            "X-Api-Resource-Id": resource_id,
            "X-Api-Request-Id": request_id,
            "Content-Type": "application/json",
        }

    raise ServiceException(
        code=450,
        message="Volcano V3 timestamps test requires audio.Volcano.api_key + resource_id, or app_id + access_token + resource_id",
    )


def _decode_debug_payload(payload: bytes) -> Any:
    if not payload:
        return None

    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError:
        return {
            "encoding": "base64",
            "data": base64.b64encode(payload).decode("ascii"),
        }

    stripped = text.strip()
    if stripped.startswith("{") or stripped.startswith("["):
        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            return text
    return text


def volcano_singleton_timestamps_test(
    text: str,
    speaker: str,
    output_path: str,
    *,
    model: Optional[str] = None,
    speech_rate: int = 0,
    loudness_rate: int = 0,
    sample_rate: int = 24000,
    audio_format: str = "mp3",
    emotion: Optional[str] = None,
    emotion_scale: Optional[int] = None,
    disable_markdown_filter: bool = False,
) -> VolcanoTimestampsDebugResult:
    volcano_config = my_config.get("audio", {}).get("Volcano", {})
    url = volcano_config.get("v3_sse_host", "https://openspeech.bytedance.com/api/v3/tts/unidirectional/sse")
    resource_id = str(volcano_config.get("resource_id", ""))
    request_id = str(uuid.uuid4())

    api_generation = "2.0" if "2.0" in resource_id else "1.0"
    enable_subtitle = api_generation == "2.0"
    enable_timestamp = api_generation == "1.0"
    timestamp_mode = "enable_subtitle" if enable_subtitle else "enable_timestamp"

    headers = _get_volcano_v3_headers(volcano_config, request_id)

    audio_params: dict[str, Any] = {
        "format": audio_format,
        "sample_rate": sample_rate,
        "speech_rate": speech_rate,
        "loudness_rate": loudness_rate,
    }
    if enable_subtitle:
        audio_params["enable_subtitle"] = True
    if enable_timestamp:
        audio_params["enable_timestamp"] = True
    if emotion:
        audio_params["emotion"] = emotion
    if emotion_scale is not None:
        audio_params["emotion_scale"] = emotion_scale

    payload: dict[str, Any] = {
        "user": {"uid": f"codex_debug_{uuid.uuid4().hex[:8]}"},
        "namespace": "BidirectionalTTS",
        "req_params": {
            "text": text,
            "speaker": speaker,
            "audio_params": audio_params,
            "additions": {"disable_markdown_filter": disable_markdown_filter},
        },
    }
    if model:
        payload["req_params"]["model"] = model

    log.info(f"Volcano singleton timestamps test request url={url}, resource_id={resource_id}, payload={payload}")

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    sentences: list[VolcanoSentenceTimestamp] = []
    raw_events: list[dict[str, Any]] = []
    audio_data = bytearray()
    usage: Optional[dict[str, Any]] = None

    with requests.Session() as session:
        response = session.post(url, headers=headers, json=payload, stream=True, timeout=(10, 300))
        try:
            response.raise_for_status()
        except requests.HTTPError as exc:
            body = response.text[:2000]
            raise ServiceException(code=450, message=f"Volcano V3 request failed: {exc}", data=body) from exc

        current_event: Optional[str] = None
        for raw_line in response.iter_lines(decode_unicode=True):
            if not raw_line:
                continue

            line = raw_line.strip()
            if line.startswith("event:"):
                current_event = line.split(":", 1)[1].strip()
                continue

            if not line.startswith("data:"):
                continue

            payload_text = line.split(":", 1)[1].strip()
            try:
                event_payload = json.loads(payload_text)
            except json.JSONDecodeError:
                log.warning(f"Unexpected non-json volcano event payload: {payload_text[:500]}")
                continue

            raw_events.append({"event": current_event, "payload": event_payload})

            if event_payload.get("data"):
                audio_data.extend(base64.b64decode(event_payload["data"]))

            sentence = _collect_sentence_from_payload(current_event, event_payload)
            if sentence:
                sentences.append(sentence)

            if event_payload.get("usage") is not None:
                usage = event_payload.get("usage")

    output.write_bytes(audio_data)
    log.info(
        f"Volcano singleton timestamps test finished: audio_bytes={len(audio_data)}, "
        f"sentences={len(sentences)}, output={output.as_posix()}"
    )

    return VolcanoTimestampsDebugResult(
        api_generation=api_generation,
        timestamp_mode=timestamp_mode,
        output_path=output.as_posix(),
        audio_bytes=len(audio_data),
        event_count=len(raw_events),
        usage=usage,
        sentences=sentences,
        raw_events=raw_events,
    )


async def volcano_generate_voice(
    voice_type,
    text,
    filename,
    speed=1.0,
    volume=1.0,
    emotion="neutral",
    emotion_active=False,
    emotion_intensity=2.5,
    debug_dump_path: Optional[str] = None,
) -> None:
    volcano_config = my_config.get("audio", {}).get("Volcano", {})
    appid = volcano_config.get("app_id") or volcano_config.get("appid")
    access_token = volcano_config.get("access_token")
    host = volcano_config.get("host", "wss://openspeech.bytedance.com/api/v1/tts/ws_binary")
    cluster = volcano_config.get("cluster", "volcano_tts")

    if not appid or not access_token:
        raise ServiceException(code=450, message="火山音频配置缺失，请检查 audio.Volcano.app_id / access_token")

    headers = {"Authorization": f"Bearer;{access_token}"}
    log.info(f"Connecting to {host} with headers: {headers}")

    websocket = await websockets.connect(host, additional_headers=headers, max_size=10 * 1024 * 1024)
    response_headers = getattr(getattr(websocket, "response", None), "headers", {})
    log.info(f"Connected to WebSocket server, Logid: {response_headers.get('x-tt-logid', '')}")

    try:
        request = {
            "app": {"appid": appid, "token": access_token, "cluster": cluster},
            "user": {"uid": str(uuid.uuid4())},
            "audio": {
                "voice_type": voice_type,
                "encoding": "wav",
                "speed_ratio": speed,
                "loudness_ratio": volume,
                "emotion": emotion,
                "enable_emotion": emotion_active,
                "emotion_intensity": emotion_intensity,
            },
            "request": {
                "reqid": str(uuid.uuid4()),
                "text": text,
                "operation": "submit",
                "with_timestamp": "1",
                "extra_param": json.dumps({"disable_markdown_filter": False}),
            },
        }
        log.info(f"{request}")
        await full_client_request(websocket, json.dumps(request).encode())

        audio_data = bytearray()
        debug_messages: list[dict[str, Any]] = []
        frontend_payloads: list[Any] = []
        while True:
            msg = await receive_message(websocket)
            decoded_payload = _decode_debug_payload(msg.payload)
            message_record: dict[str, Any] = {
                "type": msg.type.name,
                "sequence": msg.sequence,
                "event": msg.event.name if getattr(msg, "event", None) else None,
            }
            if decoded_payload is not None and msg.type != MsgType.AudioOnlyServer:
                message_record["payload"] = decoded_payload
            elif msg.type == MsgType.AudioOnlyServer:
                message_record["payload_bytes"] = len(msg.payload)
            debug_messages.append(message_record)

            if msg.type == MsgType.FrontEndResultServer:
                if decoded_payload is not None:
                    frontend_payloads.append(decoded_payload)
                continue
            if msg.type == MsgType.AudioOnlyServer:
                audio_data.extend(msg.payload)
                if msg.sequence < 0:
                    break
                continue
            raise RuntimeError(f"TTS conversion failed: {msg}")

        if not audio_data:
            raise RuntimeError("No audio data received")

        with open(filename, "wb") as f:
            f.write(audio_data)
        log.info(f"Audio received: {len(audio_data)}, saved to {filename}")

        if debug_dump_path:
            dump_path = Path(debug_dump_path)
            dump_path.parent.mkdir(parents=True, exist_ok=True)
            debug_dump = {
                "request": request,
                "host": host,
                "audio_output": filename,
                "audio_bytes": len(audio_data),
                "frontend_payloads": frontend_payloads,
                "messages": debug_messages,
            }
            dump_path.write_text(
                json.dumps(debug_dump, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            log.info(f"Debug dump written to {dump_path}")
    finally:
        await websocket.close()
        log.info("Connection closed")
