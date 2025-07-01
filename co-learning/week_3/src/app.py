import json
import requests
import os
import subprocess
import logging
from flask import Flask, render_template, request, jsonify

# --- 配置日志 ---
# 配置日志记录器，设置日志级别为INFO，并定义日志格式
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- 创建 Flask 应用实例 ---
# 确保这一行在所有 @app.route 或其他 app. 方法之前被定义
app = Flask(__name__)

# --- 配置常量 ---
# SUI 全节点 RPC 端点，优先从环境变量 SUI_RPC_ENDPOINT 获取，否则使用测试网默认值
RPC_ENDPOINT = os.getenv("SUI_RPC_ENDPOINT", "https://fullnode.testnet.sui.io:443")

# 获取交易详情的选项，确保能获取到交易的输入、效果和事件等信息
TRANSACTION_OPTIONS = {
    "showInput": True,
    "showRawInput": True,
    "showEffects": True,
    "showEvents": True,
    "showObjectChanges": True, # 关键：必须为 True 才能获取到 packageId
    "showBalanceChanges": True
}

# 挑战中需要用户提交的合约内部的 Flag，优先从环境变量 MOVE_CONTRACT_FLAG 获取
MOVE_FLAG = os.getenv("MOVE_CONTRACT_FLAG", "CTF{MoveCTF-Task2}")

# 服务器根 Flag 文件的路径，这是挑战成功的最终奖励。优先从环境变量 ROOT_FLAG_PATH 获取
# 在生产环境中，这个文件通常会通过 Docker 或其他方式挂载到指定路径
ROOT_FLAG_PATH = os.getenv("ROOT_FLAG_PATH", "/flag")

# UUID 文件（通常包含 GitHub ID）的路径，用于验证用户的身份。优先从环境变量 UUID_FILE_PATH 获取
UUID_FILE_PATH = os.getenv("UUID_FILE_PATH", "/uuid")

# Move 合约项目目录的路径，优先从环境变量 MOVE_CONTRACT_PATH 获取
MOVE_CONTRACT_PATH = os.getenv("MOVE_CONTRACT_PATH", "./move_contract")

# Sui CLI 的 Gas 预算，优先从环境变量 SUI_GAS_BUDGET 获取
SUI_GAS_BUDGET = os.getenv("SUI_GAS_BUDGET", "100000000")

# --- 全局变量（用于存储动态数据，服务器重启会丢失） ---
# 注意：在生产环境，这些值通常应该存储在数据库或持久化存储中
GLOBAL_ROOT_FLAG = "flag{INITIAL_FLAG_PLACEHOLDER}"
GLOBAL_GITHUB_ID = "0x0_PLACEHOLDER"
GLOBAL_DEPLOYED_PACKAGE_ID = None
GLOBAL_DEPLOYED_TX_HASH = None

# --- 辅助函数 ---

def _load_static_data():
    """
    在应用启动时加载静态数据，如根 Flag 和 GitHub ID。
    确保这些关键数据在应用运行时可用，避免每次请求都读取文件。
    如果文件不存在，会尝试从环境变量加载或使用默认占位符。
    """
    global GLOBAL_ROOT_FLAG
    global GLOBAL_GITHUB_ID

    # 尝试从文件加载根 Flag
    try:
        if os.path.exists(ROOT_FLAG_PATH):
            with open(ROOT_FLAG_PATH, 'r') as f:
                GLOBAL_ROOT_FLAG = f.read().strip()
                logger.info(f"成功从 {ROOT_FLAG_PATH} 加载根 Flag。")
        else:
            # 如果文件不存在，尝试从环境变量 CTF_ROOT_FLAG 获取
            logger.warning(f"Flag 文件未找到于 {ROOT_FLAG_PATH}。尝试从环境变量 CTF_ROOT_FLAG 获取。")
            GLOBAL_ROOT_FLAG = os.getenv("CTF_ROOT_FLAG", "flag{ENV_FLAG_NOT_SET}")
    except Exception as e:
        GLOBAL_ROOT_FLAG = "flag{ERROR_READING_FLAG}"
        logger.error(f"读取 Flag 文件 {ROOT_FLAG_PATH} 失败: {e}。使用占位 Flag。", exc_info=True)

    # 尝试从文件加载 GitHub ID
    try:
        if os.path.exists(UUID_FILE_PATH):
            with open(UUID_FILE_PATH, 'r') as f:
                GLOBAL_GITHUB_ID = f.read().strip()
                logger.info(f"成功从 {UUID_FILE_PATH} 加载 GitHub ID。")
        else:
            # 如果文件不存在，尝试从环境变量 GITHUB_ID 获取
            logger.warning(f"UUID 文件未找到于 {UUID_FILE_PATH}。尝试从环境变量 GITHUB_ID 获取。")
            GLOBAL_GITHUB_ID = os.getenv("GITHUB_ID", "0x0_DEFAULT_GH_ID")
    except Exception as e:
        GLOBAL_GITHUB_ID = "error_reading_uuid"
        logger.error(f"读取 UUID 文件 {UUID_FILE_PATH} 失败: {e}。使用错误占位符。", exc_info=True)

# 在应用启动时立即加载静态数据
# `with app.app_context()` 确保在 Flask 应用上下文内执行，这对于某些 Flask 扩展是必需的，
# 尽管这里直接读取文件不是严格必需的，但作为良好实践可以保留。
with app.app_context():
    logger.info("应用初始化：加载静态数据...")
    _load_static_data()


def _get_transaction_details(tx_digest: str) -> dict or None:
    """
    通过 RPC 获取指定交易哈希的详细信息。
    返回交易结果字典或 None (如果请求失败)。
    """
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "sui_getTransactionBlock",
        "params": [tx_digest, TRANSACTION_OPTIONS],
    }
    try:
        # 设置更长的超时时间，以应对网络延迟或节点繁忙
        resp = requests.post(RPC_ENDPOINT, json=payload, timeout=20)
        resp.raise_for_status()  # 如果响应状态码不是 2xx，则抛出 HTTPError 异常
        data = resp.json()
        if "error" in data:
            logger.error(f"RPC 错误：sui_getTransactionBlock for {tx_digest}: {data['error']}")
            return None
        return data.get("result")
    except requests.exceptions.Timeout:
        logger.error(f"RPC 请求超时：sui_getTransactionBlock for {tx_digest}。端点: {RPC_ENDPOINT}")
        return None
    except requests.exceptions.RequestException as e:
        logger.error(f"RPC 请求失败：sui_getTransactionBlock for {tx_digest}: {e}")
        return None
    except json.JSONDecodeError as e:
        logger.error(f"RPC 响应 JSON 解析失败：sui_getTransactionBlock for {tx_digest}: {e}")
        return None
    except Exception as e:
        logger.critical(f"获取交易详情时发生意外错误：{tx_digest}: {e}", exc_info=True)
        return None


def check_submission(tx_digest: str, user_github_id: str, expected_package_id: str) -> tuple[bool, str]:
    """
    检查用户提交的交易是否有效，并是否满足挑战要求。
    包括：交易成功、调用了正确的合约和函数、包含正确的 GitHub ID。

    Args:
        tx_digest (str): 用户提交的交易哈希。
        user_github_id (str): 当前挑战的 GitHub ID。
        expected_package_id (str): 期望被调用的合约 Package ID。

    Returns:
        tuple[bool, str]: 一个元组，第一个元素表示校验是否成功 (True/False)，
                          第二个元素是详细的校验结果或错误消息。
    """
    if not expected_package_id:
        return False, "服务器尚未部署挑战合约，无法校验。请先点击“开始挑战”部署合约。"

    tx_details = _get_transaction_details(tx_digest)
    if not tx_details:
        return False, "无法获取交易详情，请检查交易哈希是否正确或网络连接。"

    # 1. 检查交易执行是否成功
    effects = tx_details.get("effects")
    if not effects or effects.get("status", {}).get("status") != "success":
        logger.warning(f"交易 {tx_digest} 状态不成功或效果缺失。")
        return False, "交易执行失败，请检查你的交易是否成功。"

    # 2. 检查交易是否是可编程交易且包含调用信息
    transaction = tx_details.get("transaction", {}).get("data", {}).get("transaction", {})
    transaction_kind = transaction.get("kind", {})
    if transaction_kind != "ProgrammableTransaction":
        logger.warning(f"交易 {tx_digest} 不是可编程交易或缺失交易详情。")
        return False, "提交的交易不是有效的 Move 可编程交易。"

    # 3. 检查 Package ID/GitHub ID/flag
    events = tx_details.get("events", [])
    if events:
        # check package id
        tx_package_id = events[0].get("type")
        if tx_package_id != f"{expected_package_id}::flag::FlagEvent":
            logger.warning(f"PackageID 不匹配：交易 {tx_digest}。预期: {expected_package_id}, 实际: {tx_package_id}")
            return False, f"交易中的 PackageID 不匹配。请确认你的 PackageID ({tx_package_id}) 为实际部署合约。"
        first_event_parsed_json = events[0].get("parsedJson")
        if first_event_parsed_json:
            # GitHub ID
            parsed_github_id = first_event_parsed_json.get("github_id")
            if parsed_github_id == user_github_id:
                logger.info(f"交易 {tx_digest} 中的 GitHub ID 匹配: {parsed_github_id}")
            else:
                logger.warning(f"GitHub ID 不匹配：交易 {tx_digest}。预期: {user_github_id}, 实际: {parsed_github_id}")
                return False, f"交易中的 GitHub ID 不匹配。请确认你的 GitHub ID ({user_github_id}) 与交易相关联。"
            # flag
            flag = first_event_parsed_json.get("flag")
            if flag is not None:
                logger.info(f"交易 {tx_digest} 中的 flag 匹配: {flag}")
                return True, "交易校验成功。"
            else:
                logger.warning(f"flag 不匹配：交易 {tx_digest}。预期: {MOVE_FLAG}, 实际: {flag}")
                return False, f"交易中的 flag 不匹配。请确认你的 flag ({flag}) 与交易相同。"
            # if first_event_parsed_json.get("success") is True:
            #     return True, "交易校验成功。"
            # else:
            #     return False, f"交易校验失败: success=False"
        else:
            logger.warning(f"交易 {tx_digest} 的第一个事件中未找到 parsedJson。")
            return False, "交易事件数据不完整，无法验证 GitHub ID。"
    else:
        logger.warning(f"交易 {tx_digest} 中未找到任何事件。")
        return False, "交易未产生任何事件，无法验证 GitHub ID。"


def deploy_contract() -> dict:
    """
    部署 Move 合约。
    此函数执行 SUI CLI 命令来发布合约，并解析输出以获取 package_id 和 transaction_hash。
    """
    # 检查 Move 合约目录是否存在
    if not os.path.isdir(MOVE_CONTRACT_PATH):
        logger.error(f"Move 合约目录不存在: {MOVE_CONTRACT_PATH}")
        return {
            "success": False,
            "error": f"服务器上找不到 Move 合约目录: {MOVE_CONTRACT_PATH}",
            "details": "请联系管理员确保合约文件已正确部署。"
        }

    command = [
        "sui", "client", "publish",
        "--gas-budget", SUI_GAS_BUDGET,
        "--json", # 以 JSON 格式输出结果
        MOVE_CONTRACT_PATH # 合约项目路径
    ]
    try:
        logger.info(f"执行 Sui CLI 命令: {' '.join(command)}")
        # 使用 subprocess.run 运行命令并捕获标准输出和错误
        # `check=True` 会在命令返回非零退出码时抛出 CalledProcessError
        process = subprocess.run(command, capture_output=True, text=True, check=True, encoding='utf-8')
        output = process.stdout
        stderr_output = process.stderr

        if stderr_output:
            logger.warning(f"Sui CLI 命令产生了标准错误输出 (可能包含警告):\n{stderr_output}")

        # 解析 JSON 输出
        try:
            result = json.loads(output)
        except json.JSONDecodeError as e:
            logger.error(f"解析 Sui CLI 输出 JSON 失败: {e}. 原始输出: {output}")
            return {
                "success": False,
                "error": f"解析 Sui CLI 输出 JSON 失败: {e}",
                "output": output,
                "details": "Sui CLI 返回了非标准 JSON 格式或输出不完整。"
            }

        package_id = None
        transaction_hash = None

        # 从 JSON 结果中提取 transactionDigest
        transaction_hash = result.get("effects", {}).get("transactionDigest")

        # 从 objectChanges 中找到 published 类型的对象，获取 packageId
        object_changes = result.get("objectChanges", [])
        for obj_change in object_changes:
            if obj_change.get("type") == "published":
                package_id = obj_change.get("packageId")
                break

        if package_id and transaction_hash:
            # 部署成功后，更新全局变量
            global GLOBAL_DEPLOYED_PACKAGE_ID
            global GLOBAL_DEPLOYED_TX_HASH
            GLOBAL_DEPLOYED_PACKAGE_ID = package_id
            GLOBAL_DEPLOYED_TX_HASH = transaction_hash
            logger.info(f"合约部署成功。包 ID: {package_id}, 交易哈希: {transaction_hash}")
            return {
                "success": True,
                "package_id": package_id,
                "transaction_hash": transaction_hash
            }
        else:
            logger.error(f"无法从 Sui CLI 输出中解析 package_id ({package_id}) 或 transaction_hash ({transaction_hash}). 完整输出: {output}")
            return {
                "success": False,
                "error": "无法从 Sui CLI 输出中解析 package_id 或 transaction_hash。",
                "output": output,
                "details": "Sui CLI 输出格式不符合预期，请检查 Sui 版本或网络响应。"
            }

    except subprocess.CalledProcessError as e:
        # 捕获 CLI 命令执行失败的错误
        logger.error(f"Sui CLI 命令执行失败，退出码: {e.returncode}")
        logger.error(f"Stdout: {e.stdout}")
        logger.error(f"Stderr: {e.stderr}")
        return {
            "success": False,
            "error": f"Sui CLI 命令执行失败: {e.stderr or e.stdout}",
            "command": ' '.join(command),
            "details": "这可能是由于 Sui CLI 配置问题、钱包余额不足或合约编译错误导致。"
        }
    except FileNotFoundError:
        logger.error("Sui CLI 命令 'sui' 未找到。请确保 'sui' 已安装并配置在 PATH 中。")
        return {
            "success": False,
            "error": "Sui CLI 命令 'sui' 未找到。",
            "details": "请确保 Sui CLI 已安装并配置在系统 PATH 中。尝试在终端运行 'sui client --version' 检查。"
        }
    except Exception as e:
        # 捕获所有其他未知错误，并打印堆栈信息
        logger.critical(f"部署合约时发生未知错误: {e}", exc_info=True)
        return {
            "success": False,
            "error": f"部署合约时发生未知错误: {e}",
            "details": "请检查服务器日志获取更多信息。"
        }

# --- Flask 路由 ---

@app.route("/", methods=["GET", "POST"])
def index():
    """
    根路由：处理欢迎页显示和 Flag 提交逻辑。
    用户在此页面提交交易哈希和合约 Flag。
    """
    github_id = GLOBAL_GITHUB_ID # 直接使用全局变量
    result_message = ""
    flag_message = ""

    # 传递已部署的合约 ID 和交易哈希给前端，如果尚未部署，则显示相应占位符
    deployed_package_id_for_frontend = GLOBAL_DEPLOYED_PACKAGE_ID or "未部署合约"
    deployed_tx_hash_for_frontend = GLOBAL_DEPLOYED_TX_HASH or "无"

    if request.method == "POST":
        tx_digest = request.form.get("tx_digest", "").strip()
        contract_flag_input = request.form.get("contract_flag_input", "").strip()

        if not tx_digest:
            result_message = "错误：交易哈希不能为空！"
            logger.warning("提交失败：交易哈希为空。")
        elif not GLOBAL_DEPLOYED_PACKAGE_ID:
            # 如果合约尚未部署，则无法验证交易
            result_message = "错误：服务器尚未部署挑战合约，无法验证交易。请先点击“开始挑战”按钮部署合约。"
            logger.error("尝试在没有部署合约 ID 的情况下检查交易。")
        else:
            # 调用 check_submission 函数来处理所有校验逻辑
            is_tx_valid, validation_message = check_submission(
                tx_digest, GLOBAL_GITHUB_ID, GLOBAL_DEPLOYED_PACKAGE_ID
            )
            is_contract_flag_match = (contract_flag_input == MOVE_FLAG)

            if is_tx_valid and is_contract_flag_match:
                final_flag = GLOBAL_ROOT_FLAG # 直接使用全局变量
                result_message = "恭喜！所有校验通过！"
                flag_message = f"你的 Flag 是：<span class='text-green-500 font-bold'>{final_flag}</span> 请移步平台提交。"
                logger.info(f"挑战成功完成，GitHub ID: {github_id}, 交易哈希: {tx_digest}")
            else:
                messages = []
                if not is_tx_valid:
                    messages.append(validation_message) # 使用 check_submission 返回的详细消息
                if not is_contract_flag_match:
                    messages.append("合约返回的 Flag 不正确。")

                result_message = " ".join(messages)
                logger.warning(f"挑战失败，GitHub ID: {github_id}, 交易哈希: {tx_digest}。原因: {result_message}")

    return render_template(
        "index.html",
        github_id=github_id,
        result_message=result_message,
        flag_message=flag_message,
        deployed_package_id=deployed_package_id_for_frontend, # 传递给前端显示
        deployed_tx_hash=deployed_tx_hash_for_frontend # 传递部署交易哈希给前端
    )

@app.route("/start_challenge", methods=["POST"])
def start_challenge():
    """
    处理用户点击“开始挑战”的请求。
    此路由负责部署 Move 合约并返回部署结果。
    """
    logger.info("收到开始挑战请求。")

    # 部署策略：如果已经部署过，默认不再重复部署。
    # 如果需要强制重新部署，可以添加一个查询参数或清除全局变量的机制。
    if GLOBAL_DEPLOYED_PACKAGE_ID and GLOBAL_DEPLOYED_PACKAGE_ID != "未部署合约":
        logger.info(f"合约已部署 (Package ID: {GLOBAL_DEPLOYED_PACKAGE_ID})，不再重复部署。")
        return jsonify({
            "status": "success",
            "message": "合约已部署！请使用现有合约进行挑战。",
            "package_id": GLOBAL_DEPLOYED_PACKAGE_ID,
            "transaction_hash": GLOBAL_DEPLOYED_TX_HASH or "（请查看上次部署的日志获取交易哈希）"
        })

    deployment_result = deploy_contract() # deploy_contract 会更新 GLOBAL_DEPLOYED_PACKAGE_ID 和 GLOBAL_DEPLOYED_TX_HASH

    if deployment_result["success"]:
        logger.info(f"合约部署成功。包 ID: {GLOBAL_DEPLOYED_PACKAGE_ID}")
        return jsonify({
            "status": "success",
            "message": "合约部署成功！",
            "package_id": GLOBAL_DEPLOYED_PACKAGE_ID, # 从全局变量获取
            "transaction_hash": GLOBAL_DEPLOYED_TX_HASH # 从全局变量获取
        })
    else:
        logger.error(f"合约部署失败: {deployment_result.get('error', '未知错误')}. 详情: {deployment_result.get('details', '')}")
        return jsonify({
            "status": "error",
            "message": f"合约部署失败: {deployment_result.get('error', '未知错误')}",
            "details": deployment_result.get('details', '请检查服务器日志获取更多信息。') # 返回更详细的错误原因
        }), 500

if __name__ == "__main__":
    # 在生产环境中，请不要使用 debug=True，它会暴露敏感信息且性能较差。
    # 请使用 Gunicorn 或 uWSGI 等 WSGI 服务器来运行 Flask 应用。
    # app.run() 的默认端口是 5000，如果 8080 端口已被占用，或希望使用默认端口，可以省略 port=8080。
    app.run(host="0.0.0.0", port=8080, debug=True)
