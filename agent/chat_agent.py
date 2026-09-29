"""
Chat Agent — Autonomous function-calling agent loop via OpenRouter.
Maintains state, searches faculty, scrapes emails, creates interactive draft cards,
and streams SSE events in real-time.
"""
import json
import time
import requests
from typing import Dict, List, Generator, Any
from agent.faculty_search import FacultySearcher
from agent.email_sender import EmailSender

searcher = FacultySearcher()

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_professors",
            "description": "Search for university professors and research faculty whose work aligns with given topics and target regions (US, Singapore, Hong Kong, UK, Canada, Europe, Australia). Returns name, affiliation, h-index, key papers, and discovered emails.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Research topics, e.g. 'computer vision diffusion models' or 'LLM reasoning agentic AI'"
                    },
                    "regions": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of regions: 'us', 'singapore', 'hong_kong', 'uk', 'canada', 'europe', 'australia'"
                    },
                    "universities": {
                        "type": "string",
                        "description": "Optional comma-separated universities to filter by, e.g. 'Stanford, MIT, NUS, HKUST'"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max number of professors to return (default 4)"
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "scrape_professor_email",
            "description": "Scrape or look up the contact email for a specific professor given their homepage URL, name, and university.",
            "parameters": {
                "type": "object",
                "properties": {
                    "professor_name": {"type": "string"},
                    "affiliation": {"type": "string"},
                    "homepage_url": {"type": "string"}
                },
                "required": ["professor_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_email_draft",
            "description": "Create an interactive email draft card for the user. Fill out professor email, compelling subject line, friend CC email, full personalized cold email body citing their specific papers, and attached resumes.",
            "parameters": {
                "type": "object",
                "properties": {
                    "professor_name": {
                        "type": "string",
                        "description": "Name of the professor"
                    },
                    "professor_email": {
                        "type": "string",
                        "description": "Professor's verified or deduced email address"
                    },
                    "affiliation": {
                        "type": "string",
                        "description": "University or Department name"
                    },
                    "h_index": {
                        "type": "integer",
                        "description": "Estimated h-index or impact metric"
                    },
                    "subject": {
                        "type": "string",
                        "description": "Highly tailored, academic, non-spammy subject line referencing their specific research field"
                    },
                    "body": {
                        "type": "string",
                        "description": "Full personalized cold email body (under 250 words) including greeting, paper reference, introduction of student and their friend (CC'd), research synergy, mention of attached resumes, and polite call to action."
                    },
                    "key_papers": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of 1-3 specific paper titles cited or relevant to this professor"
                    },
                    "homepage": {
                        "type": "string",
                        "description": "Professor's homepage or scholar URL"
                    }
                },
                "required": ["professor_name", "subject", "body"]
            }
        }
    }
]

class ChatAgent:
    OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

    def __init__(self, api_key: str, model: str, user_config: dict = None):
        self.api_key = api_key.strip()
        self.model = model.strip() or "nvidia/nemotron-3.5-lightning:free"
        self.user_config = user_config or {}

    def get_system_prompt(self) -> str:
        sender = self.user_config.get("sender_email", "")
        cc = self.user_config.get("cc_email", "")
        name = self.user_config.get("student_name", "Student")
        friend = self.user_config.get("friend_name", "Research Partner")
        resumes = self.user_config.get("available_resumes", [])
        resume_str = ", ".join(resumes) if resumes else "Student_Resume.pdf, Friend_Resume.pdf"

        return f"""You are the Autonomous Research Outreach Agent. Your mission is to help {name} and their research partner {friend} find leading university professors whose lab and research align with their passions, and draft highly tailored, high-converting cold emails for research internships, MS/PhD openings, or collaboration.

## Target Geography
The users are targeting US, Singapore (NUS, NTU, SUTD), Hong Kong (HKU, HKUST, CUHK), UK, Canada, and Europe in AI, Machine Learning, Computer Vision, NLP, Robotics, and allied fields.

## Configured User Information
- Primary Student: {name} (Email: {sender})
- Research Partner (Always CC'd): {friend} (CC: {cc})
- Attached Resumes: {resume_str}

## Your Autonomous Tools
1. **search_professors**: Search faculty by topic, regions (['us', 'singapore', 'hong_kong']), and universities.
2. **scrape_professor_email**: Discover or deduce professor email addresses.
3. **create_email_draft**: Generate an interactive draft card with editable fields: professor email, subject, friend CC, customized email body, and resume attachments.

## Workflow Rules
1. When the user asks to find professors, call `search_professors` with their topic and regions.
2. When professors are found, present a clear, enthusiastic summary of each candidate.
3. Automatically call `create_email_draft` for the top matching professors so the user gets an interactive draft card right in the chat.
4. In every email body:
   - Keep length concise (under 250 words).
   - Cite 1-2 specific papers by the professor to demonstrate genuine research interest.
   - Introduce both {name} and {friend} (mentioning {friend} is CC'd).
   - Explicitly mention that both of their resumes are attached for review.
   - Conclude with a humble, clear inquiry (e.g. asking if they have 15 minutes to chat or any available research positions).
5. Always be polite, encouraging, and highly competent. If information like email is uncertain, let the user know they can edit it directly in the interactive draft card."""

    def chat_stream(self, messages: List[Dict]) -> Generator[Dict, None, None]:
        """Run the agent loop, streaming events."""
        max_iterations = 12

        # Ensure system prompt is present
        formatted_messages = []
        has_system = any(m.get("role") == "system" for m in messages)
        if not has_system:
            formatted_messages.append({"role": "system", "content": self.get_system_prompt()})

        for m in messages:
            formatted_messages.append(m)

        for iteration in range(max_iterations):
            try:
                response = self._call_llm(formatted_messages)
            except Exception as e:
                yield {"type": "error", "content": f"OpenRouter API Error: {str(e)}"}
                return

            choices = response.get("choices", [])
            if not choices:
                yield {"type": "error", "content": "No response received from model."}
                return

            msg = choices[0].get("message", {})
            content = msg.get("content") or ""
            tool_calls = msg.get("tool_calls") or []

            # Check if model output plain text tool call format (e.g. fallback for models without native tools)
            if not tool_calls and "<tool_call>" in content:
                tool_calls = self._parse_text_tool_calls(content)

            if tool_calls:
                formatted_messages.append({
                    "role": "assistant",
                    "content": content,
                    "tool_calls": tool_calls
                })

                if content:
                    yield {"type": "message", "content": content}

                for tc in tool_calls:
                    func = tc.get("function", {})
                    func_name = func.get("name", "")
                    raw_args = func.get("arguments", "{}")
                    try:
                        args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                    except Exception:
                        args = {}

                    yield {"type": "tool_start", "name": func_name, "args": args}

                    result = self._execute_tool(func_name, args)

                    # Emit interactive draft card for create_email_draft
                    if func_name == "create_email_draft":
                        draft_obj = dict(args)
                        draft_obj["cc_email"] = draft_obj.get("cc_email") or self.user_config.get("cc_email", "")
                        draft_obj["attachments"] = self.user_config.get("available_resumes", ["Student_Resume.pdf", "Friend_Resume.pdf"])
                        yield {"type": "draft", "draft": draft_obj}

                    yield {"type": "tool_result", "name": func_name, "result": result}

                    formatted_messages.append({
                        "role": "tool",
                        "tool_call_id": tc.get("id", f"call_{int(time.time()*1000)}"),
                        "content": json.dumps(result, default=str)
                    })

                time.sleep(0.3)
                continue
            else:
                if content:
                    yield {"type": "message", "content": content}
                    formatted_messages.append({"role": "assistant", "content": content})
                break

        yield {"type": "done"}

    def _call_llm(self, messages: List[Dict]) -> dict:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "http://127.0.0.1:5000",
            "X-Title": "Research Outreach Agent",
        }
        body = {
            "model": self.model,
            "messages": messages,
            "tools": TOOLS,
            "temperature": 0.7,
            "max_tokens": 4096,
        }
        resp = requests.post(self.OPENROUTER_URL, headers=headers, json=body, timeout=120)
        if resp.status_code != 200:
            raise RuntimeError(f"OpenRouter Error ({resp.status_code}): {resp.text[:500]}")
        return resp.json()

    def _parse_text_tool_calls(self, text: str) -> List[Dict]:
        calls = []
        matches = re.findall(r"<tool_call>(.*?)</tool_call>", text, re.DOTALL)
        for idx, m in enumerate(matches):
            try:
                data = json.loads(m.strip())
                calls.append({
                    "id": f"text_call_{idx}",
                    "type": "function",
                    "function": {
                        "name": data.get("name"),
                        "arguments": json.dumps(data.get("arguments", {}))
                    }
                })
            except Exception:
                pass
        return calls

    def _execute_tool(self, name: str, args: dict) -> dict:
        if name == "search_professors":
            query = args.get("query", "")
            regions = args.get("regions", ["us", "singapore", "hong_kong"])
            universities = args.get("universities", "")
            limit = args.get("limit", 4)
            res = searcher.search(query, regions=regions, universities=universities, limit=limit)
            return res

        elif name == "scrape_professor_email":
            homepage = args.get("homepage_url", "")
            prof_name = args.get("professor_name", "")
            affiliation = args.get("affiliation", "")
            email = searcher.get_author_email(homepage, prof_name, affiliation)
            return {"success": True, "email": email, "professor": prof_name}

        elif name == "create_email_draft":
            prof_name = args.get("professor_name", "Professor")
            return {
                "success": True,
                "message": f"Interactive email draft generated for {prof_name}. Rendered in user interface for review and sending."
            }

        return {"success": False, "error": f"Tool '{name}' not found."}
