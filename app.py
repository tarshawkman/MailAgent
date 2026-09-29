"""
Research Outreach Agent — Autonomous Chat & Cold Email Execution Server
Features:
- Chat-centric interface with OpenRouter free model function-calling
- SSE real-time streaming of thoughts, tools, and interactive draft cards
- Auto-loads credentials from .env
- Direct SMTP email dispatch with multiple resume attachments & CC support
"""

import os
import json
import time
import requests
from flask import Flask, render_template, request, jsonify, Response
from dotenv import load_dotenv, set_key

from agent.chat_agent import ChatAgent
from agent.email_sender import EmailSender

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_PATH = os.path.join(BASE_DIR, ".env")
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Ensure sample starter resumes exist if empty
sample1 = os.path.join(UPLOAD_DIR, "Aaditya_Saraf_Resume.pdf")
sample2 = os.path.join(UPLOAD_DIR, "Friend_Research_CV.pdf")
if not os.path.exists(sample1):
    with open(sample1, "w", encoding="utf-8") as f:
        f.write("%PDF-1.4 [Sample Resume: Aaditya Saraf - Research in Computer Vision & AI]")
if not os.path.exists(sample2):
    with open(sample2, "w", encoding="utf-8") as f:
        f.write("%PDF-1.4 [Sample Resume: Research Partner - Research in AI & ML]")

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 32 * 1024 * 1024


def get_all_env_config():
    """Load and normalize settings from .env file."""
    load_dotenv(ENV_PATH, override=True)

    def get_val(*keys, default=""):
        for k in keys:
            v = os.getenv(k)
            if v is not None and str(v).strip():
                return str(v).strip()
        return default

    openrouter_key = get_val("openrouter", "OPENROUTER", "OPENROUTER_API_KEY", "openrouter_key")
    sender_email = get_val("sender-email", "sender_email", "SENDER_EMAIL", "EMAIL_SENDER")
    app_password = get_val("app-password", "app_password", "APP_PASSWORD", "EMAIL_APP_PASSWORD")
    cc_email = get_val("cc-email", "cc_email", "CC_EMAIL", "friend-email", "friend_email")
    student_name = get_val("student_name", "student-name", "STUDENT_NAME", "name", default="Aaditya Saraf")
    friend_name = get_val("friend_name", "friend-name", "FRIEND_NAME", default="Research Partner")

    resumes = [f for f in os.listdir(UPLOAD_DIR) if os.path.isfile(os.path.join(UPLOAD_DIR, f))]

    return {
        "openrouter_key": openrouter_key,
        "has_openrouter": bool(openrouter_key),
        "sender_email": sender_email,
        "has_sender_email": bool(sender_email),
        "app_password": app_password,
        "has_app_password": bool(app_password),
        "cc_email": cc_email,
        "student_name": student_name,
        "friend_name": friend_name,
        "available_resumes": resumes,
    }


_cached_models = []
_cache_time = 0


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/config", methods=["GET"])
def get_config():
    cfg = get_all_env_config()
    masked_key = (cfg["openrouter_key"][:8] + "..." + cfg["openrouter_key"][-4:]) if len(cfg["openrouter_key"]) > 12 else ("Configured" if cfg["has_openrouter"] else "")
    return jsonify({
        "success": True,
        "has_openrouter": cfg["has_openrouter"],
        "masked_openrouter": masked_key,
        "sender_email": cfg["sender_email"],
        "has_app_password": cfg["has_app_password"],
        "cc_email": cfg["cc_email"],
        "student_name": cfg["student_name"],
        "friend_name": cfg["friend_name"],
        "available_resumes": cfg["available_resumes"],
    })


@app.route("/api/config", methods=["POST"])
def update_config():
    data = request.json or {}
    updated = {}

    if "cc_email" in data:
        set_key(ENV_PATH, "cc-email", data["cc_email"].strip())
        updated["cc_email"] = data["cc_email"].strip()

    if "student_name" in data:
        set_key(ENV_PATH, "student_name", data["student_name"].strip())
        updated["student_name"] = data["student_name"].strip()

    if "friend_name" in data:
        set_key(ENV_PATH, "friend_name", data["friend_name"].strip())
        updated["friend_name"] = data["friend_name"].strip()

    if "sender_email" in data and data["sender_email"].strip():
        set_key(ENV_PATH, "sender-email", data["sender_email"].strip())
        updated["sender_email"] = data["sender_email"].strip()

    if "app_password" in data and data["app_password"].strip():
        set_key(ENV_PATH, "app-password", data["app_password"].strip())
        updated["has_app_password"] = True

    if "openrouter_key" in data and data["openrouter_key"].strip():
        set_key(ENV_PATH, "openrouter", data["openrouter_key"].strip())
        updated["has_openrouter"] = True

    return jsonify({"success": True, "updated": updated, "config": get_all_env_config()})


@app.route("/api/free-models", methods=["GET"])
def get_free_models():
    global _cached_models, _cache_time
    now = time.time()
    if _cached_models and (now - _cache_time < 300):
        return jsonify({"success": True, "models": _cached_models})

    try:
        resp = requests.get("https://openrouter.ai/api/v1/models", timeout=15)
        if resp.status_code == 200:
            data = resp.json().get("data", [])
            free_models = []
            for m in data:
                mid = m.get("id", "")
                if mid.endswith(":free"):
                    params = m.get("supported_parameters", [])
                    has_tools = "tools" in params or "tool_choice" in params
                    free_models.append({
                        "id": mid,
                        "name": m.get("name", mid),
                        "context_length": m.get("context_length", 4096),
                        "has_tools": has_tools,
                        "description": m.get("description", ""),
                    })

            free_models.sort(key=lambda x: (not x["has_tools"], x["name"].lower()))
            _cached_models = free_models
            _cache_time = now
            return jsonify({"success": True, "models": free_models})
    except Exception:
        pass

    fallback = [
        {"id": "nvidia/nemotron-3.5-lightning:free", "name": "NVIDIA: Nemotron 3.5 Lightning (free)", "has_tools": True},
        {"id": "qwen/qwen3.8-27b:free", "name": "Qwen: Qwen3.8 27B (free)", "has_tools": True},
        {"id": "google/gemma-4-31b-it:free", "name": "Google: Gemma 4 31B (free)", "has_tools": True},
        {"id": "google/gemma-4-26b-a4b-it:free", "name": "Google: Gemma 4 26B A4B (free)", "has_tools": True},
        {"id": "inclusionai/ling-3.0-flash-sante:free", "name": "inclusionAI: Ling 3.0 Flash Sante (free)", "has_tools": True},
        {"id": "cohere/north-mini-code:free", "name": "Cohere: North Mini Code (free)", "has_tools": True},
    ]
    return jsonify({"success": True, "models": fallback})


@app.route("/api/chat/stream", methods=["POST"])
def chat_stream():
    """SSE streaming endpoint for agent chat conversation."""
    data = request.json or {}
    messages = data.get("messages", [])
    selected_model = data.get("model", "nvidia/nemotron-3.5-lightning:free")

    cfg = get_all_env_config()
    api_key = data.get("api_key") or cfg["openrouter_key"]

    if not api_key:
        return jsonify({
            "success": False,
            "error": "OpenRouter API Key not found. Please ensure 'openrouter' is set in your .env file."
        }), 400

    if not messages:
        return jsonify({"success": False, "error": "No chat messages provided."}), 400

    agent = ChatAgent(api_key=api_key, model=selected_model, user_config=cfg)

    def event_generator():
        for event in agent.chat_stream(messages):
            yield f"data: {json.dumps(event)}\n\n"

    return Response(event_generator(), mimetype="text/event-stream")


@app.route("/api/draft/send", methods=["POST"])
def send_draft():
    """Send an approved cold email draft via SMTP."""
    data = request.json or {}
    to_email = data.get("to_email", "").strip()
    cc_email = data.get("cc_email", "").strip()
    subject = data.get("subject", "").strip()
    body = data.get("body", "").strip()
    attachments = data.get("attachments", [])

    cfg = get_all_env_config()
    sender_email = data.get("sender_email") or cfg["sender_email"]
    app_password = data.get("app_password") or cfg["app_password"]
    sender_name = data.get("sender_name") or cfg["student_name"]

    if not sender_email or not app_password:
        return jsonify({
            "success": False,
            "error": "Sender email or app-password missing in .env. Please configure them in the sidebar."
        }), 400

    if not to_email or not body:
        return jsonify({
            "success": False,
            "error": "Recipient email and email body are required."
        }), 400

    full_attachment_paths = []
    if isinstance(attachments, list):
        for att in attachments:
            if isinstance(att, str):
                path = os.path.join(UPLOAD_DIR, os.path.basename(att))
                if os.path.isfile(path):
                    full_attachment_paths.append(path)

    if not full_attachment_paths and cfg["available_resumes"]:
        for res_name in cfg["available_resumes"]:
            path = os.path.join(UPLOAD_DIR, res_name)
            if os.path.isfile(path):
                full_attachment_paths.append(path)

    sender = EmailSender(email=sender_email, password=app_password)
    result = sender.send(
        to_email=to_email,
        cc_email=cc_email,
        subject=subject,
        body=body,
        attachments=full_attachment_paths,
        sender_name=sender_name,
    )
    return jsonify(result)


@app.route("/api/resumes", methods=["GET"])
def list_resumes():
    resumes = [f for f in os.listdir(UPLOAD_DIR) if os.path.isfile(os.path.join(UPLOAD_DIR, f))]
    return jsonify({"success": True, "resumes": resumes})


@app.route("/api/upload-resume", methods=["POST"])
def upload_resume():
    if "file" not in request.files:
        return jsonify({"success": False, "error": "No file uploaded."}), 400

    file = request.files["file"]
    if not file.filename:
        return jsonify({"success": False, "error": "Empty filename."}), 400

    fname = os.path.basename(file.filename)
    dest = os.path.join(UPLOAD_DIR, fname)
    file.save(dest)

    resumes = [f for f in os.listdir(UPLOAD_DIR) if os.path.isfile(os.path.join(UPLOAD_DIR, f))]
    return jsonify({"success": True, "filename": fname, "resumes": resumes})


if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5000)
