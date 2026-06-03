from .transcode_task import process_transcode_task
from .normalize_video_tasks import process_video_task
from .sprite_tasks import process_sprite_task
from .alivoice_tasks import process_alivoice_queue
from .volcovoice_tasks import process_volcovoice_queue

process_functions = {
    "mix": process_video_task,
    "transcode": process_transcode_task,
    "sprite": process_sprite_task,
    "voice": process_alivoice_queue,
    "volcovoice": process_volcovoice_queue,
}
