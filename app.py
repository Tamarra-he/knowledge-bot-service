# FORCE_DEPLOY_20260724
import os
import requests
import json
import logging
from flask import Flask, request
from monthly_report import generate_monthly_report

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# 环境变量
APP_ID = os.getenv("APP_ID")
APP_SECRET = os.getenv("APP_SECRET")
VERIFICATION_TOKEN = os.getenv("VERIFICATION_TOKEN")


@app.route("/", methods=["GET"])
def health_check():
    logger.info("✅ 健康检查")
    return "Bot Service Running OK", 200


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
        
        if msg_type != "text":
            return {"msg": "忽略"}, 200
        
        content_raw = message.get("content", "{}")
        content = json.loads(content_raw)
        user_text = content.get("text", "").strip()
        
        logger.info(f"💬 用户消息: {user_text}")
        
        # ========== 命令解析 ==========
        if user_text.startswith("/"):
            parts = user_text.split()
            command = parts[0].lower()
            
            # ---- 月报生成 ----
            if command in ["/月报", "/monthly", "/report"]:
                send_reply(sender_id, "📊 开始生成知识月报，请稍候...")
                result = generate_monthly_report()
                
                if result["success"]:
                    msg = f"""✅ 月报生成成功！

📊 知识总数：{result['knowledge_count']} 条
📅 月份：{result['year']}年{result['month']}月
📁 文件：{result['file']}

📈 核心指标：
• 总动态阅读量：{result['extra_metrics']['dynamic_read_curr']}
• 文章视频覆盖率：{result['extra_metrics']['curr_article_video_rate']:.2%}
• 本月新增知识：{result.get('new_count', 0)} 篇
"""
                    send_reply(sender_id, msg)
                else:
                    send_reply(sender_id, f"❌ 月报生成失败：{result['error']}")
                return {"status": "ok"}, 200
            
            # ---- 帮助 ----
            elif command in ["/帮助", "/help"]:
                help_text = """📖 知识月报机器人使用帮助

【可用命令】
/月报  或 /monthly   - 生成知识月报
/help  或 /帮助       - 显示本帮助

【使用说明】
1. 直接发送 /月报 即可生成当月月报
2. 生成结果会通过本消息回复

【数据要求】
请确保以下文件已上传到服务器：
- 帮助教程.md
- 含阅读量列表.xlsx
- 上月帮助教程.xlsx（可选）

有问题请联系管理员。"""
                send_reply(sender_id, help_text)
                return {"status": "ok"}, 200
            
            else:
                send_reply(sender_id, f"❌ 未知命令：{command}\n发送 /帮助 查看可用命令")
                return {"status": "ok"}, 200
        
        # 非命令消息
        else:
            send_reply(sender_id, f"""👋 你好！我是知识月报机器人。

我可以帮你自动生成知识月报。

试试发送：
• /月报  - 生成当月知识月报
• /帮助  - 查看详细帮助

有其他问题请直接联系管理员。""")
        
        return {"status": "ok"}, 200
        
    except Exception as e:
        logger.error(f"❌ 错误: {e}")
        import traceback
        traceback.print_exc()
        return {"msg": "error"}, 200


def send_reply(open_id, text):
    """发送回复消息"""
    try:
        token_res = requests.post(
            "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
            json={"app_id": APP_ID, "app_secret": APP_SECRET},
            timeout=10
        )
        token_data = token_res.json()
        if token_data.get("code") != 0:
            logger.error(f"Token获取失败: {token_data}")
            return
        
        token = token_data.get("tenant_access_token")
        
        send_res = requests.post(
            "https://open.feishu.cn/open-apis/im/v1/messages",
            params={"receive_id_type": "open_id"},
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            },
            json={
                "receive_id": open_id,
                "msg_type": "text",
                "content": json.dumps({"text": text})
            },
            timeout=10
        )
        logger.info(f"📤 消息已发送")
    except Exception as e:
        logger.error(f"❌ 发送回复失败: {e}")


if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("🚀 知识月报机器人启动")
    logger.info(f"📱 APP_ID: {APP_ID[:15] if APP_ID else 'NOT SET'}...")
    logger.info("=" * 60)
    app.run(host="0.0.0.0", port=8080, debug=False)
