import redis.asyncio as redis
from config.config import *
from utils.log_utils import logger as log
import os

redis_client = redis.Redis(host=my_config["cache"][ENV]["host"], port=my_config["cache"][ENV]["port"],
                           password=my_config["cache"][ENV]["password"], decode_responses=True, db = my_config["cache"][ENV]["database"])  # 注意 host="cache"（服务名）
