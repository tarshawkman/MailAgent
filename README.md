# 🎓 Research Outreach Agent

AI-powered tool to **find professors**, **generate personalised cold emails**, and **send them** — all for free.

![Python](https://img.shields.io/badge/Python-3.10+-blue)
![Flask](https://img.shields.io/badge/Flask-3.x-green)
![Cost](https://img.shields.io/badge/Cost-$0-brightgreen)

---

## ✨ Features

| Feature | How it works |
|---|---|
| **Faculty Search** | Queries [Semantic Scholar](https://www.semanticscholar.org/) (free, no key needed) for papers matching your interests, then batch-fetches author details (affiliations, h-index, homepage). Filters by region / specific universities. |
| **Email Generation** | Sends professor + your context to a free LLM via [OpenRouter](https://openrouter.ai/) (Gemini Flash, Llama 3.1, Qwen 2.5 — all free). Generates a personalised, research-specific cold email. |
| **Email Sending** | Sends via SMTP (Gmail App Password, Outlook, Yahoo). Supports CC (your friend), resume/CV attachment. |
| **Email Finder** | Scrapes a professor's homepage for `mailto:` links and email patterns. |
| **Settings Persistence** | Your configuration is saved in `localStorage` — no re-entering every time. |

---

## 🚀 Quick Start

### 1. Clone & install

```bash
cd research-outreach-agent
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

### 2. Get your (free) keys

| Key | Where | Notes |
|---|---|---|
| **OpenRouter API Key** | [openrouter.ai/keys](https://openrouter.ai/keys) | Sign up → create key → select free models |
| **Gmail App Password** | [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords) | Enable 2FA first, then create an "App Password" for "Mail" |

### 3. Run

```bash
python app.py
```

Open **http://127.0.0.1:5000** in your browser.

---

## 🛠️ How to Use

1. **Setup** — Paste your OpenRouter key, SMTP credentials, your info, and your friend's email.
2. **Search** — Enter research interests (e.g. "reinforcement learning agents"), pick target regions (🇺🇸 🇸🇬 🇭🇰), optionally list specific universities.
3. **Results** — Browse matching professors. Click "Find Email" to auto-scrape their homepage. Click "Compose Email" to proceed.
4. **Compose** — Hit "Generate Email" for an AI-crafted, personalised cold email. Edit it however you like.
5. **Send** — Enter the professor's email, attach your resume, review, and send. Your friend is auto-CC'd.

---

## 📁 Project Structure

```
research-outreach-agent/
├── app.py                  # Flask backend (4 API endpoints)
├── requirements.txt
├── .env.example
├── agent/
│   ├── faculty_search.py   # Semantic Scholar search + region filtering
│   ├── llm_client.py       # OpenRouter LLM integration
│   └── email_sender.py     # SMTP email with CC + attachment
├── templates/
│   └── index.html          # Single-page wizard UI
└── static/
    ├── css/style.css        # Dark theme design system
    └── js/app.js            # Frontend state + API calls
```

---

## ⚙️ Configuration

All settings are entered in the browser UI. Alternatively, copy `.env.example` → `.env` and fill in defaults:

```env
OPENROUTER_API_KEY=sk-or-v1-...
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_EMAIL=you@gmail.com
SMTP_PASSWORD=abcd efgh ijkl mnop
```

### Gmail App Password (step-by-step)

1. Go to [Google Account → Security](https://myaccount.google.com/security)
2. Enable **2-Step Verification** if not already on
3. Go to [App Passwords](https://myaccount.google.com/apppasswords)
4. Select **Mail** → **Windows Computer** → **Generate**
5. Copy the 16-character password into the app

---

## 💰 Cost

**$0.** Everything uses free tiers:

- **Semantic Scholar API** — free, no key required (rate-limited to 100 req / 5 min)
- **OpenRouter** — free models (Gemini Flash, Llama 3.1, Qwen 2.5)
- **SMTP** — your existing email account

---

## 📝 License

MIT — use it however you want.
