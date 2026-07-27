#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
知识月报机器人 - 主服务
"""

import os
import json
import requests
import logging
import re
from pathlib import Path
from flask import Flask, request
import threading

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

APP_ID = os.getenv("APP_ID")
APP_SECRET = os.getenv("APP_SECRET")
VERIFICATION_TOKEN = os.getenv("VERIFICATION_TOKEN")


# ==========================================
# 懒加载函数
# ==========================================
def get_knowledge_parser():
    try:
        from knowledge_parser import generate_knowledge_list
        logger.info("✅ knowledge_parser 加载成功")
        return generate_knowledge_list
    except ImportError as e:
        logger.error(f"❌ knowledge_parser 导入失败: {e}")
        return None


# ==========================================
# 路由
# ==========================================

@app.route("/", methods=["GET"])
def health_check():
    return "知识月报机器人运行正常 ✅", 200


@app.route("/webhook", methods=["POST"])
def feishu_webhook():
    logger.info("=" * 60)
    logger.info("📨 收到webhook请求")
    
    try:
        data = request.get_json()
        
        # URL验证
        if data.get("type") == "url_verification":
            logger.info("🔍 URL验证")
            return {"challenge": data["challenge"]}
        
        # 解析消息
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
            return handle_text_message(sender_id, user_text)
        
        # 处理文件消息 - 直接提示改用云文档
        elif msg_type == "file":
            logger.info("📎 收到文件消息（不再处理）")
            send_reply(sender_id, "⚠️ 请改用云文档方式：\n\n1. 把 帮助教程.md 上传到飞书云文档\n2. 复制文档链接发给我")
            return {"status": "ok"}, 200
        
        else:
            logger.info(f"⏭️ 忽略消息类型: {msg_type}")
            return {"msg": "忽略"}, 200
        
    except Exception as e:
        logger.error(f"❌ 处理消息异常: {e}")
        import traceback
        traceback.print_exc()
        return {"msg": "error"}, 200


# ==========================================
# 消息处理函数
# ==========================================

def handle_text_message(sender_id, text):
    """处理文本消息（命令）"""
    
    logger.info(f"📝 处理文本: {text}")
    
    # 帮助命令
    if text in ["/帮助", "/help"]:
        help_text = """📖 知识月报机器人使用帮助

【使用方法】
  1. 把 帮助教程.md 上传到飞书云文档
  2. 复制文档链接发给我
  3. 我返回 知识清单.xlsx

【命令】
  /帮助    - 显示本帮助

有问题请联系管理员。"""
        send_reply(sender_id, help_text)
        return {"status": "ok"}, 200
    
    # 检测云文档链接
    logger.info("🔍 检测云文档链接...")
    doc_match = re.search(r'https?://[^\s]+\.feishu\.cn/(docx|sheets|wiki|document)/([^\s?]+)', text, re.IGNORECASE)
    logger.info(f"🔍 匹配结果: {doc_match}")
    
    if doc_match:
        doc_type = doc_match.group(1)
        doc_token = doc_match.group(2).split('?')[0]
        doc_token = doc_token.split('#')[0]
        logger.info(f"📄 检测到云文档: type={doc_type}, token={doc_token}")
        
        send_reply(sender_id, "📄 收到云文档链接，正在读取内容...")
        threading.Thread(target=handle_doc_link, args=(sender_id, doc_type, doc_token)).start()
        return {"status": "ok"}, 200
    
    # 无意义消息
    else:
        reply = """👋 你好！我是知识文档解析助手。

📌 请把 帮助教程.md 上传到飞书云文档，然后把链接发给我。

发送 /帮助 查看详细说明"""
        send_reply(sender_id, reply)
        return {"status": "ok"}, 200


# ==========================================
# 云文档处理函数（异步）
# ==========================================

def handle_doc_link(sender_id, doc_type, doc_token):
    """处理云文档链接（异步）"""
    try:
        send_reply(sender_id, "📄 正在读取云文档内容...")
        
        doc_content = read_feishu_document(doc_type, doc_token)
        
        if doc_content is None:
            send_reply(sender_id, "❌ 读取云文档失败，请检查：\n1. 文档是否已添加机器人为协作者\n2. 文档链接是否正确")
            return
        
        if len(doc_content.strip()) < 50:
            send_reply(sender_id, f"❌ 文档内容为空或过短（{len(doc_content)}字符），请检查文档内容")
            return
        
        generate_knowledge_list = get_knowledge_parser()
        if generate_knowledge_list is None:
            send_reply(sender_id, "❌ 解析引擎加载失败，请联系管理员")
            return
        
        send_reply(sender_id, "📊 正在生成知识清单，请稍候...（可能需要1-2分钟）")
        result = generate_knowledge_list(doc_content, f"云文档_{doc_token}")
        
        if not result["success"]:
            send_reply(sender_id, f"❌ 生成失败：{result['error']}")
            return
        
        send_reply(sender_id, f"✅ 知识清单生成完成！共 {result['count']} 条知识")
        send_file(sender_id, result["file_path"])
        
    except Exception as e:
        logger.error(f"处理云文档异常: {e}")
        import traceback
        traceback.print_exc()
        send_reply(sender_id, f"❌ 处理失败: {str(e)[:100]}")


# ==========================================
# 飞书云文档API
# ==========================================

def read_feishu_document(doc_type, doc_token):
    """读取飞书云文档内容"""
    try:
        token = get_tenant_access_token()
        if not token:
            logger.error("获取Token失败")
            return None
        
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        
        # 知识库（Wiki）
        if doc_type == "wiki":
            # 获取知识库空间下的节点列表
            url = f"https://open.feishu.cn/open-apis/wiki/v2/spaces/{doc_token}/nodes"
            res = requests.get(url, headers=headers, timeout=30)
            logger.info(f"📥 Wiki API 响应: {res.status_code}")
            
            if res.status_code == 200:
                data = res.json()
                if data.get("code") == 0:
                    nodes = data.get("data", {}).get("items", [])
                    text_parts = []
                    for node in nodes:
                        title = node.get("title", "")
                        if title:
                            text_parts.append(f"# {title}")
                    content = "\n".join(text_parts)
                    logger.info(f"📄 读取Wiki成功，共 {len(content)} 字符")
                    return content
                else:
                    logger.error(f"Wiki API 返回错误: {data}")
                    return None
            else:
                logger.error(f"Wiki API HTTP错误: {res.status_code}, {res.text[:200]}")
                return None
        
        # 文档（Docx）
        elif doc_type == "docx":
            url = f"https://open.feishu.cn/open-apis/docx/v1/documents/{doc_token}/blocks"
            res = requests.get(url, headers=headers, timeout=30)
            
            if res.status_code == 200:
                data = res.json()
                if data.get("code") == 0:
                    blocks = data.get("data", {}).get("items", [])
                    text_parts = []
                    for block in blocks:
                        block_type = block.get("block_type", 0)
                        if block_type in [1, 2, 3]:
                            text = block.get("text", "")
                            if text:
                                text_parts.append(text)
                    content = "\n".join(text_parts)
                    logger.info(f"📄 读取文档成功，共 {len(content)} 字符")
                    return content
                else:
                    logger.error(f"文档API返回错误: {data}")
                    return None
            else:
                logger.error(f"文档API HTTP错误: {res.status_code}")
                return None
        
        # 表格
        elif doc_type == "sheets":
            url = f"https://open.feishu.cn/open-apis/sheets/v2/spreadsheets/{doc_token}/values/Sheet1"
            res = requests.get(url, headers=headers, timeout=30)
            if res.status_code == 200:
                data = res.json()
                if data.get("code") == 0:
                    values = data.get("data", {}).get("valueRange", {}).get("values", [])
                    text_parts = []
                    for row in values:
                        text_parts.append(" | ".join([str(cell) for cell in row if cell]))
                    content = "\n".join(text_parts)
                    return content
            return None
        
        else:
            logger.error(f"不支持的文档类型: {doc_type}")
            return None
            
    except Exception as e:
        logger.error(f"读取云文档异常: {e}")
        import traceback
        traceback.print_exc()
        return None


# ==========================================
# 飞书API工具函数
# ==========================================

def get_tenant_access_token():
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


def send_reply(open_id, text):
    """发送文本回复"""
    try:
        token = get_tenant_access_token()
        if not token:
            logger.error("发送消息失败: 无法获取Token")
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
            send_reply(open_id, "❌ 获取Token失败")
            return
        
        # 1. 上传文件
        upload_url = "https://open.feishu.cn/open-apis/im/v1/files"
        headers = {"Authorization": f"Bearer {token}"}
        
        file_name = Path(file_path).name
        logger.info(f"📤 上传文件: {file_name}")
        
        with open(file_path, 'rb') as f:
            files = {'file': (file_name, f, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')}
            res = requests.post(upload_url, headers=headers, files=files, timeout=30)
        
        result = res.json()
        if result.get("code") != 0:
            logger.error(f"上传失败: {result}")
            send_reply(open_id, "❌ 上传文件失败")
            return
        
        file_token = result.get("data", {}).get("file_token")
        if not file_token:
            send_reply(open_id, "❌ 上传文件失败")
            return
        
        # 2. 发送文件
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
        
        res = requests.post(send_url, params={"receive_id_type": "open_id"}, headers=headers, json=data, timeout=10)
        result = res.json()
        if result.get("code") == 0:
            logger.info("✅ 文件发送成功")
        else:
            logger.error(f"发送文件失败: {result}")
            send_reply(open_id, "❌ 发送文件失败")
            
    except Exception as e:
        logger.error(f"发送文件异常: {e}")
        import traceback
        traceback.print_exc()
        send_reply(open_id, f"❌ 发送失败: {str(e)[:100]}")


# ==========================================
# 启动
# ==========================================

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    logger.info("=" * 60)
    logger.info("🚀 知识月报机器人启动")
    logger.info(f"📱 APP_ID: {APP_ID[:15] if APP_ID else 'NOT SET'}...")
    logger.info("=" * 60)
    app.run(host="0.0.0.0", port=port, debug=False)
