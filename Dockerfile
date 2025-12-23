# 使用官方 Python 3.12 基础镜像
FROM python:3.12

# 删除所有默认源，强制使用阿里云
RUN rm -f /etc/apt/sources.list /etc/apt/sources.list.d/* && \
    echo "deb https://mirrors.aliyun.com/debian/ bookworm main non-free non-free-firmware" > /etc/apt/sources.list && \
    echo "deb https://mirrors.aliyun.com/debian/ bookworm-updates main non-free non-free-firmware" >> /etc/apt/sources.list && \
    echo "deb https://mirrors.aliyun.com/debian-security/ bookworm-security main non-free non-free-firmware" >> /etc/apt/sources.list \

# 安装基础工具
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    bzip2 \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*
#RUN wget https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-linux64-gpl.tar.xz -O ffmpeg.tar.xz && \
# 替代apt安装FFmpeg的步骤
# 下载并安装 FFmpeg

# 设置清华 pip 镜像源
RUN pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple

# 复制代码文件
COPY . /app
WORKDIR /app/src

# 安装依赖（使用conda-forge的ffmpeg）
RUN pip install --timeout=600 \
    -r requirements.txt

# 暴露端口
EXPOSE 5000


# 启动命令
CMD ["uvicorn", "FastAPI_server:app", "--host", "0.0.0.0", "--port", "5000"]