import json
import requests
import os
from flask import Flask, render_template, request, redirect, url_for

app = Flask(__name__)

# --- 配置常量 ---
# SUI RPC 端点
RPC_ENDPOINT = "https://fullnode.testnet.sui.io:443"

# SUI 交易查询选项
OPTIONS = {
    "showInput": True,
    "showRawInput": True,
    "showEffects": True,
    "showEvents": True,
    "showObjectChanges": True,
    "showBalanceChanges": True
}

# 合约中硬编码的 FLAG 值（可选，用于额外校验）
# 挑战者提交的“合约返回的FLAG”需要与此值匹配
MOVE_FLAG = "CTF{Letsmovectf_week1}"

# 根目录下的 FLAG 文件路径
# 最终需要获得的 Flag 将从这个文件中读取
ROOT_FLAG_PATH = "/flag"

UUID_FILE_PATH = "/uuid"

# --- 辅助函数 ---

def check_success(tx_digest: str, github_id: str) -> bool:
    """
    检查 SUI 交易是否成功且 github_id 匹配。
    根据提供的逻辑，它会尝试从交易事件中解析出 github_id 并进行比对。
    """
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "sui_getTransactionBlock",
        "params": [tx_digest, OPTIONS],
    }

    try:
        resp = requests.post(RPC_ENDPOINT, json=payload, timeout=10)
        resp.raise_for_status()  # 如果响应状态码不是 2xx，则抛出异常
        data = resp.json()

        if "error" in data:
            print(f"RPC error for tx_digest {tx_digest}: {data['error']}")
            return False

        # 检查交易执行是否成功
        if data["result"]["effects"]["status"]["status"] != "success":
            print(f"Transaction {tx_digest} status is not success.")
            return False

        # 检查事件中是否存在 github_id 并匹配
        # 这里假设 github_id 位于第一个事件的 parsedJson 字段中
        if data["result"]["events"] and data["result"]["events"][0]["parsedJson"]:
            parsed_github_id = data["result"]["events"][0]["parsedJson"].get("github_id")
            if parsed_github_id == github_id:
                print(f"Transaction {tx_digest} successful and github_id matched: {parsed_github_id}")
                return True
            else:
                print(f"github_id mismatch. Expected: {github_id}, Got: {parsed_github_id}")
                return False
        else:
            print(f"No events or parsedJson found in transaction {tx_digest}.")
            return False

    except requests.exceptions.RequestException as e:
        print(f"RPC request failed: {e}")
        return False
    except KeyError as e:
        print(f"Missing expected key in RPC response: {e}")
        return False
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return False

def get_root_flag() -> str:
    """
    尝试从根目录下的 /flag 文件中读取 Flag。
    如果文件不存在或无法读取，则返回一个占位符。
    """
    try:
        with open(ROOT_FLAG_PATH, 'r') as f:
            return f.read().strip()
    except FileNotFoundError:
        print(f"Error: Flag file not found at {ROOT_FLAG_PATH}")
        return "flag{FLAG_NOT_FOUND_ON_SERVER}"
    except Exception as e:
        print(f"Error reading flag file: {e}")
        return "flag{ERROR_READING_FLAG}"
    
def get_github_id() -> str:
    """
    从根目录的 uuid 文件中读取 GitHub ID。
    如果文件不存在或无法读取，则返回一个占位符。
    """
    try:
        with open(UUID_FILE_PATH, 'r') as f:
            return f.read().strip()
    except FileNotFoundError:
        print(f"Error: UUID file not found at {UUID_FILE_PATH}")
        return "sahuang"
    except Exception as e:
        print(f"Error reading UUID file: {e}")
        return "error_reading_uuid"

# --- Flask 路由 ---

@app.route("/", methods=["GET", "POST"])
def index():
    """
    根路由：处理欢迎页显示和 Flag 提交。
    """
    GITHUB_ID = get_github_id()  # 从文件中读取 GitHub ID
    result_message = ""
    flag_message = ""

    if request.method == "POST":
        tx_digest = request.form.get("tx_digest", "").strip()
        contract_flag_input = request.form.get("contract_flag_input", "").strip()

        if not tx_digest:
            result_message = "错误：交易哈希不能为空！"
        else:
            # 1. 校验交易哈希和 GitHub ID
            is_tx_success = check_success(tx_digest, GITHUB_ID)

            # 2. 校验合约返回的 Flag
            is_contract_flag_match = (contract_flag_input == MOVE_FLAG)

            if is_tx_success and is_contract_flag_match:
                final_flag = get_root_flag()
                result_message = "恭喜！所有校验通过！"
                flag_message = f"你的 Flag 是：<span class='text-green-500 font-bold'>{final_flag}</span> 请移步平台提交。"
            else:
                if not is_tx_success:
                    result_message += "交易哈希或 Github ID 校验失败。请检查交易详情和你的 Github ID 是否正确。"
                if not is_contract_flag_match:
                    result_message += " 合约返回的 Flag 不正确。"
                if is_tx_success and not is_contract_flag_match:
                    result_message = "交易哈希校验成功，但合约返回的 Flag 不正确。"
                elif not is_tx_success and is_contract_flag_match:
                    result_message = "合约返回的 Flag 校验成功，但交易哈希或 Github ID 校验失败。"

    return render_template(
        "index.html",
        github_id=GITHUB_ID,
        result_message=result_message,
        flag_message=flag_message
    )

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)