"""
LLM Client — talks to OpenRouter (free-tier models) to generate personalised
cold-emails to professors, and dynamically fetches available free models.
"""

import requests
from typing import Dict, List


class LLMClient:
    OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
    MODELS_URL = "https://openrouter.ai/api/v1/models"

    FALLBACK_FREE_MODELS = [
        {"id": "google/gemini-2.0-flash-exp:free", "name": "Google: Gemini Flash 2.0 Exp (Free)"},
        {"id": "meta-llama/llama-3.1-8b-instruct:free", "name": "Meta: Llama 3.1 8B Instruct (Free)"},
        {"id": "qwen/qwen-2.5-7b-instruct:free", "name": "Qwen 2.5 7B Instruct (Free)"},
        {"id": "deepseek/deepseek-r1:free", "name": "DeepSeek R1 (Free)"},
        {"id": "mistralai/mistral-7b-instruct:free", "name": "Mistral 7B Instruct (Free)"}
    ]

    def __init__(self, api_key: str, model: str | None = None):
        self.api_key = api_key
        self.model = model or "google/gemini-2.0-flash-exp:free"

    @classmethod
    def fetch_free_models(cls) -> List[Dict]:
        """Fetch all free models dynamically from OpenRouter API."""
        try:
            resp = requests.get(cls.MODELS_URL, timeout=10)
            if resp.status_code == 200:
                data = resp.json().get("data", [])
                free_models = []
                for m in data:
                    mid = m.get("id", "")
                    mname = m.get("name", mid)
                    pricing = m.get("pricing", {})
                    prompt_price = float(pricing.get("prompt", 1))
                    comp_price = float(pricing.get("completion", 1))

                    if mid.endswith(":free") or (prompt_price == 0 and comp_price == 0):
                        free_models.append({
                            "id": mid,
                            "name": f"{mname} (Free)" if "(free)" not in mname.lower() else mname
                        })

                if free_models:
                    # Sort alphabetically by name
                    return sorted(free_models, key=lambda x: x["name"])
        except Exception:
            pass
        return cls.FALLBACK_FREE_MODELS

    def generate_cold_email(self, professor: Dict, user_info: Dict) -> Dict:
        """Return {"success": bool, "subject": str, "body": str}."""
        prof_ctx = self._professor_context(professor)

        prompt = f"""You are an expert at writing cold emails to university professors seeking research opportunities.
Write a professional, personalised cold email based on the information below.

Professor Info:
{prof_ctx}

Student Info:
Name            : {user_info.get("name", "Student")}
Current Status  : {user_info.get("status", "Undergraduate student")}
University      : {user_info.get("university", "")}
Research Interest: {user_info.get("interests", "AI / ML")}
Experience       : {user_info.get("experience", "")}
Friend (CC'd)   : {user_info.get("friend_name", "my colleague")}

Rules:
1. Produce a compelling SUBJECT line.
2. Open with genuine interest in a *specific* paper or research thread.
3. Briefly introduce the sender and the CC'd friend (both seeking research positions).
4. Explain alignment between the professor's work and the sender's interests.
5. Mention the attached resume / CV.
6. Express interest in RA / visiting researcher / PhD openings.
7. Body must be under 250 words, professional yet warm.

Return the email in EXACTLY this format (no extra markdown):

SUBJECT: <subject line>
---
<body text>"""

        try:
            raw = self._call(prompt)
            return self._parse(raw)
        except Exception as exc:
            return {"success": False, "error": str(exc), "subject": "", "body": ""}

    @staticmethod
    def _professor_context(prof: Dict) -> str:
        lines = [f"Name        : {prof.get('name', 'Unknown')}"]
        affs = prof.get("affiliations") or []
        if affs:
            lines.append(f"Affiliation : {', '.join(affs)}")
        h = prof.get("hIndex")
        if h:
            lines.append(f"h-index     : {h}")
        papers = prof.get("papers", [])
        if papers:
            lines.append("Key papers  :")
            for p in papers[:3]:
                cit = p.get("citations", 0)
                yr = p.get("year", "")
                lines.append(f'  • "{p.get("title", "")}" ({yr}, {cit} cit.)')
        return "\n".join(lines)

    def _call(self, prompt: str) -> str:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "http://localhost:5000",
            "X-Title": "Research Outreach Agent",
        }
        body = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are an expert academic email writer. You craft "
                        "personalised, compelling cold emails to professors."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.7,
            "max_tokens": 1024,
        }
        resp = requests.post(
            self.OPENROUTER_URL, headers=headers, json=body, timeout=90
        )
        if resp.status_code != 200:
            raise RuntimeError(
                f"OpenRouter {resp.status_code}: {resp.text[:300]}"
            )
        return resp.json()["choices"][0]["message"]["content"]

    @staticmethod
    def _parse(text: str) -> Dict:
        subject, body = "", text
        if "SUBJECT:" in text:
            parts = text.split("---", 1)
            subject = parts[0].replace("SUBJECT:", "").strip()
            if len(parts) > 1:
                body = parts[1].strip()
        return {"success": True, "subject": subject, "body": body}
