from api.v1.stack import stack_router
from api.v1.video import video_router
from api.v1.process import process_router
from api.v1.test import test_router
from api.v1.sprite import sprite_router
from api.v1.transcode import transcode_router
from api.v1.evaluate_memory_cost import memory_evaluate_router
from api.v1.audio import audio_router

all_router = [stack_router, video_router, process_router, test_router,sprite_router, transcode_router, memory_evaluate_router, audio_router]