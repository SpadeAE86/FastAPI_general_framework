# 使用自制的python3.12 包含ffmpeg rocketmq的基础镜像
FROM swr.cn-east-3.myhuaweicloud.com/freeuuu/python312-ffmpeg:2.1

# 复制代码文件
COPY . /app
WORKDIR /app

#从requirements.txt里安装依赖
RUN pip install --timeout=600 \
    -r requirements.txt


WORKDIR /app/src


# 暴露端口
EXPOSE 5000

RUN which sw-python || echo "sw-python NOT FOUND"
# 启动命令
CMD ["sw-python","run","gunicorn","FastAPI_server:app","-k","uvicorn.workers.UvicornWorker","-w","1","-b","0.0.0.0:5000"]
