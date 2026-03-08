# FastAPI_general_framework
basic framework and major component of FastAPI
cd 到 src文件夹
服务后端启动使用 uvicorn FastAPI_server:app --host 0.0.0.0 --port 8004 --reload
dispatcher启动 python .\core\dispatcher\run.py
celery启动使用 
local config:
redis port: 6379
rabbitmq:
    host: 123.60.104.114
    port: 5672
    username: root
    password: RootDev123
    vhost: /
    use_ssl: false
    management_port: 15672