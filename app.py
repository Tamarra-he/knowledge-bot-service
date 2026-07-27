#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
知识月报机器人 - 主服务（简化测试版）
"""

import os
import json
import requests
import logging
from flask import Flask, request

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

APP_ID = os.getenv("APP_ID")
APP_SECRET = os.getenv("APP_SECRET")
VERIFICATION_TOKEN = os.getenv("VERIFICATION_TOKEN")


@app.route("/", methods=["GET"])
def health_check():
    logger.info("✅ 健康检查")
    return "知识月报机器人运行正常 ✅", 200


@app.route("/webhook", methods=["POST"])
def feishu_webhook():
    logger.info("📨 收到webhook请求")
    
    try:
        data = request.get_json()
        
        if data.get("type") == "url_verification":
            logger.info("🔍 URL验证")
            return {"challenge": data["challenge"]}
        
        header = data.get("header", {})
        event_type = header.get("event_type")
        
        if event_type != "im.message.receive_v1":
            return {"msg": "忽略"}, 200
        
        event = data.get("event", {})
        message = event.get("message", {})
        sender = event.get("sender", {})
        sender_id = sender.get("sender_id", {}).get("open_id")
        msg_type = message.get("message_type")
        
        # 处理文本消息
        if msg_type == "text":
            content_raw = message.get("content", "{}")
            content = json.loads(content_raw)
            user_text = content.get("text", "").strip()
            logger.info(f"💬 用户消息: {user_text}")
            
            if user_text in ["/帮助", "/help"]:
                send_reply(sender_id, "📖 发送 .md 文件给我，我帮你生成知识清单")
            else:
                send_reply(sender_id, "👋 你好！发送 .md 文件给我，我帮你生成知识清单")
            return {"status": "ok"}, 200
        
        # 处理文件消息
        elif msg_type == "file":
            logger.info("📎 收到文件")
            content_raw = message.get("content", "{}")
            content = json.loads(content_raw)
            file_token = content.get("file_token")
            file_name = content.get("file_name", "")
            
            send_reply(sender_id, f"📄 收到文件: {file_name}，功能开发中...")
            return {"status": "ok"}, 200
        
        return {"msg": "忽略"}, 200
        
    except Exception as e:
        logger.error(f"❌ 错误: {e}")
        return {"msg": "error"}, 200


def get_tenant_access_token():
    try:
        url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
        res = requests.post(url, json={"app_id": APP_ID, "app_secret": APP_SECRET}, timeout=10)
        data = res.json()
        if data.get("code") == 0:
            return data.get("tenant_access_token")
        return None
    except Exception as e:
        logger.error(f"获取Token异常: {e}")
        return None


def send_reply(open_id, text):
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
        
        res = requests.post(url, params={"receive_id_type": "open_id"}, headers=headers, json=data, timeout=10)
        if res.json().get("code") == 0:
            logger.info("✅ 消息发送成功")
    except Exception as e:
        logger.error(f"发送消息异常: {e}")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    logger.info("🚀 启动服务...")
    app.run(host="0.0.0.0", port=port, debug=False)
