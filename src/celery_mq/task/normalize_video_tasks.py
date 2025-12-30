from datetime import datetime
from celery_mq.celery_app import celery_app
from models.pydantic_models.request.mixed_video_request import MixedVideoRequest, ratio_option
from core.normalize_process_pool import *
from utils.general_utils import *
from core.caption import *
import json
from service.mixed_video_service import mixed_video_service

@celery_app.task(queue="video_queue")
async def process_video_task(mixed_config: MixedVideoRequest):
    resp = await mixed_video_service(mixed_config)
    return resp