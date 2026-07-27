#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
知识月报机器人 - 主服务
"""

import os
import re
import json
import requests
import logging
from pathlib import Path
from flask import Flask, request

from knowledge_parser import generate_knowledge_list

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# ==================== 环境变量 ====================
APP_ID = os.getenv("APP_ID")
APP_SECRET = os.getenv("APP_SECRET")
VERIFICATION_TOKEN = os.getenv("VERIFICATION_TOKEN")


# ==================== 路由 ====================

@app.route("/", methods=["GET"])
def health_check():
    logger.info("✅ 健康检查")
    return "知识月报机器人运行正常 ✅", 200


@app.route("/webhook", methods=["POST"])
def feishu_webhook():
    """
    飞书消息接收入口
    """
    logger.info("=" * 60)
    logger.info("📨 收到webhook请求")
    
    try:
        data = request.get_json()
        
        # 1. URL验证（首次配置时飞书会发送）
        if data.get("type") == "url_verification":
            logger.info("🔍 URL验证")
            return {"challenge": data["challenge"]}
        
        # 2. 解析消息
        header = data.get("header", {})
        event_type = header.get("event_type")
        
        if event_type != "im.message.receive_v1":
            return {"msg": "忽略"}, 200
        
        event = data.get("event", {})
        message = event.get("message", {})
        sender = event.get("sender", {})
        sender_id = sender.get("sender_id", {}).get("open_id")
        msg_type = message.get("message_type")
        chat_type = message.get("chat_type")
        
        # 3. 只处理文本消息和文件消息
        if msg_type not in ["text", "file"]:
            return {"msg": "忽略"}, 200
        
        # 4. 处理消息
        if msg_type == "text":
            content_raw = message.get("content", "{}")
            content = json.loads(content_raw)
            user_text = content.get("text", "").strip()
            logger.info(f"💬 用户消息: {user_text}")
            return handle_text_message(sender_id, user_text)
        
        elif msg_type == "file":
            content_raw = message.get("content", "{}")
            content = json.loads(content_raw)
            file_token = content.get("file_token")
            file_name = content.get("file_name", "")
            logger.info(f"📎 收到文件: {file_name}")
            return handle_file_message(sender_id, file_token, file_name)
        
        return {"status": "ok"}, 200
        
    except Exception as e:
        logger.error(f"❌ 处理消息异常: {e}")
        import traceback
        traceback.print_exc()
        return {"msg": "error"}, 200


# ==================== 消息处理函数 ====================

def handle_text_message(sender_id, text):
    """处理文本消息（命令）"""
    
    # 帮助命令
    if text in ["/帮助", "/help"]:
        help_text = """📖 知识月报机器人使用帮助

【可用命令】
直接发送文件：
  📄 .md文件 → 生成知识清单
  📊 .xlsx文件 → 会话问题分类

【其他命令】
  /健康度  - 执行健康度检测（即将上线）
  /帮助    - 显示本帮助

【使用示例】
  1. 导出 帮助教程.md
  2. 在飞书发给本机器人
  3. 收到 知识清单.xlsx

有问题请联系管理员。"""
        send_reply(sender_id, help_text)
        return {"status": "ok"}, 200
    
    # 健康度命令（预留）
    if text in ["/健康度", "/health"]:
        send_reply(sender_id, "🔍 健康度检测功能开发中，敬请期待...")
        return {"status": "ok"}, 200
    
    # 无意义消息
    else:
        reply = """👋 你好！我是知识月报机器人。

我能帮你：
✅ 把 .md 文件转成 Excel 知识清单

试试这样用：
1. 在知识后台导出 帮助教程.md
2. 把文件发给我
3. 我返回 知识清单.xlsx

发送 /帮助 查看完整帮助"""
        send_reply(sender_id, reply)
        return {"status": "ok"}, 200


def handle_file_message(sender_id, file_token, file_name):
    """处理文件消息"""
    
    # 1. 检查文件类型
    if not file_name.endswith(".md"):
        send_reply(sender_id, f"❌ 暂不支持 {file_name} 格式，请发送 .md 文件")
        return {"status": "ok"}, 200
    
    # 2. 下载文件
    send_reply(sender_id, "📄 收到文件，正在下载...")
    file_content = download_feishu_file(file_token)
    
    if file_content is None:
        send_reply(sender_id, "❌ 文件下载失败，请稍后重试")
        return {"status": "ok"}, 200
    
    # 3. 生成知识清单
    send_reply(sender_id, "📊 正在生成知识清单，请稍候...")
    result = generate_knowledge_list(file_content, file_name)
    
    if not result["success"]:
        send_reply(sender_id, f"❌ 生成失败：{result['error']}")
        return {"status": "ok"}, 200
    
    # 4. 发送结果
    send_reply(sender_id, f"✅ 知识清单生成完成！共 {result['count']} 条知识")
    
    # 发送文件
    send_file(sender_id, result["file_path"])
    
    return {"status": "ok"}, 200


# ==================== 飞书API工具函数 ====================

def get_tenant_access_token():
    """获取飞书tenant_access_token"""
    try:
        url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
        res = requests.post(url, json={"app_id": APP_ID, "app_secret": APP_SECRET}, timeout=10)
        data = res.json()
        if data.get("code") == 0:
            return data.get("tenant_access_token")
        else:
            logger.error(f"获取Token失败: {data}")
            return None
    except Exception as e:
        logger.error(f"获取Token异常: {e}")
        return None


def download_feishu_file(file_token):
    """下载飞书消息中的文件"""
    try:
        token = get_tenant_access_token()
        if not token:
            return None
        
        url = f"https://open.feishu.cn/open-apis/drive/v1/files/{file_token}/download"
        headers = {"Authorization": f"Bearer {token}"}
        
        res = requests.get(url, headers=headers, timeout=30)
        
        if res.status_code == 200:
            # 尝试解码为文本
            try:
                return res.text
            except:
                # 如果是二进制文件，返回None
                logger.error("文件不是文本格式")
                return None
        else:
            logger.error(f"下载文件失败: {res.status_code}")
            return None
    except Exception as e:
        logger.error(f"下载文件异常: {e}")
        return None


def send_reply(open_id, text):
    """发送文本回复"""
    try:
        token = get_tenant_access_token()
        if not token:
            return
        
        url = "https://open.feishu.cn/open-apis/im/v1/messages"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        data = {
            "receive_id": open_id,
            "msg_type": "text",
            "content": json.dumps({"text": text})
        }
        
        res = requests.post(
            url,
            params={"receive_id_type": "open_id"},
            headers=headers,
            json=data,
            timeout=10
        )
        result = res.json()
        if result.get("code") == 0:
            logger.info("✅ 消息发送成功")
        else:
            logger.error(f"发送消息失败: {result}")
    except Exception as e:
        logger.error(f"发送消息异常: {e}")


def send_file(open_id, file_path):
    """发送文件"""
    try:
        token = get_tenant_access_token()
        if not token:
            return
        
        # 1. 上传文件获取file_token
        upload_url = "https://open.feishu.cn/open-apis/im/v1/files"
        headers = {"Authorization": f"Bearer {token}"}
        
        with open(file_path, 'rb') as f:
            files = {'file': (Path(file_path).name, f, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')}
            res = requests.post(upload_url, headers=headers, files=files, timeout=30)
        
        result = res.json()
        if result.get("code") != 0:
            logger.error(f"上传文件失败: {result}")
            return
        
        file_token = result.get("data", {}).get("file_token")
        
        # 2. 发送文件消息
        send_url = "https://open.feishu.cn/open-apis/im/v1/messages"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        data = {
            "receive_id": open_id,
            "msg_type": "file",
            "content": json.dumps({"file_token": file_token})
        }
        
        res = requests.post(
            send_url,
            params={"receive_id_type": "open_id"},
            headers=headers,
            json=data,
            timeout=10
        )
        result = res.json()
        if result.get("code") == 0:
            logger.info("✅ 文件发送成功")
        else:
            logger.error(f"发送文件失败: {result}")
    except Exception as e:
        logger.error(f"发送文件异常: {e}")


# ==================== 启动 ====================

if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("🚀 知识月报机器人启动")
    logger.info(f"📱 APP_ID: {APP_ID[:15] if APP_ID else 'NOT SET'}...")
    logger.info("=" * 60)
    app.run(host="0.0.0.0", port=8080, debug=False)
