#!/bin/sh

# 写入 flag
echo "$FLAG" | tee /flag
FLAG=no_flag
chmod 744 /flag

# 生成 uuid 
cat /proc/sys/kernel/random/uuid > /uuid
chmod 744 /uuid

chmod -R 755 /app


# 启动Flask应用交互
cd /app && python3 app.py