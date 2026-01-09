from api.v1.stack import stack_router
from api.v1.video import video_router
from api.v1.process import process_router
from api.v1.test import test_router

all_router = [stack_router, video_router, process_router, test_router]