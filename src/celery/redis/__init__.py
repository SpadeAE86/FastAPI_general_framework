import redis.asyncio as redis
from config.config import *
from utils.log_utils import logger as log
import os

redis_client = redis.Redis(host=my_config["redis"][ENV]["host"], port=my_config["redis"][ENV]["port"],
                           password=my_config["redis"][ENV]["password"], decode_responses=True, db = my_config["redis"][ENV]["database"])  # 注意 host="redis"（服务名）
