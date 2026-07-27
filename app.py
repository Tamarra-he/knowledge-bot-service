from flask import Flask, request, jsonify
import os
import json
import requests
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

APP_ID = os.getenv("APP_ID", "")
APP_SECRET = os.getenv("APP_SECRET", "")
VERIFICATION_TOKEN = os.getenv("VERIFICATION_TOKEN", "")


@app.route("/", methods=["GET"])
def health():
    return "OK", 200


@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        data = request.get_json()
        logger.info(f"📨 收到请求: {data.get('type') if data else 'no data'}")
        
        # URL验证
        if data and data.get("type") == "url_verification":
            logger.info("🔍 URL验证")
            return {"challenge": data["challenge"]}
        
        return {"msg": "ok"}, 200
    except Exception as e:
        logger.error(f"❌ 错误: {e}")
        return {"msg": "error"}, 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    logger.info("🚀 启动服务...")
    app.run(host="0.0.0.0", port=port, debug=False)
