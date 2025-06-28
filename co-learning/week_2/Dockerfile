FROM mysten/sui-tools:testnet

# 制作者信息
LABEL auther_template="cyclens-probius"

ENV DEBIAN_FRONTEND=noninteractive

# 更换 apt 镜像源并更新软件包列表
RUN sed -i 's|deb.debian.org|mirrors.ustc.edu.cn|g' /etc/apt/sources.list && \
    sed -i 's|security.debian.org|mirrors.ustc.edu.cn|g' /etc/apt/sources.list && \
    apt-get update

RUN apt-get install -y python3 python3-pip && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# 安装必要的 Python 依赖库
RUN python3 -m pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple \
    flask requests

COPY sui_config /root/.sui/sui_config/

# 设置工作目录
WORKDIR /app

# 复制应用代码
COPY src/ /app/
COPY move_contract /app/move_contract/

RUN git clone https://github.com/MystenLabs/sui.git /app/sui

# 复制入口点脚本并设置权限
COPY service/docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

# 暴露端口
EXPOSE 8080

# 设置入口点
ENTRYPOINT ["/docker-entrypoint.sh"]