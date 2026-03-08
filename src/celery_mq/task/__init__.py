from .transcode_task import process_transcode_task
from .normalize_video_tasks import process_video_task
from .sprite_tasks import process_sprite_task

process_functions = {
    "mix": process_video_task,
    "transcode": process_transcode_task,
    "sprite": process_sprite_task
}