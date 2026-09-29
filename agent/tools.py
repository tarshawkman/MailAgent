"""
Tools module for Research Outreach Agent.
Wraps core sub-systems into structured tools for the autonomous agent.
"""

from typing import Dict, List, Optional
from agent.faculty_search import FacultySearcher
from agent.llm_client import LLMClient

searcher = FacultySearcher()

TOOL_DESCRIPTIONS = [
    {
        "name": "search_faculty",
        "description": "Searches Semantic Scholar for university faculty matching research interests and region constraints.",
        "parameters": {
            "type": "object",
            "properties": {
                "interests": {"type": "string", "description": "Research topics, e.g., Computer Vision, LLMs, NLP"},
                "regions": {"type": "array", "items": {"type": "string"}, "description": "Target regions e.g. ['us', 'singapore', 'hong_kong']"},
                "universities": {"type": "string", "description": "Optional university filter"},
                "limit": {"type": "integer", "description": "Number of results to retrieve"}
            },
            "required": ["interests"]
        }
    },
    {
        "name": "scrape_faculty_email",
        "description": "Scrapes a professor's homepage or academic site to discover their email address.",
        "parameters": {
            "type": "object",
            "properties": {
                "homepage_url": {"type": "string", "description": "Professor's homepage URL"}
            },
            "required": ["homepage_url"]
        }
    },
    {
        "name": "draft_cold_email",
        "description": "Uses LLM to craft a personalized cold email for a specific professor based on their paper titles and student profile.",
        "parameters": {
            "type": "object",
            "properties": {
                "professor": {"type": "object"},
                "user_info": {"type": "object"}
            },
            "required": ["professor", "user_info"]
        }
    }
]

def execute_tool(tool_name: str, tool_args: Dict, api_key: str = "", model: str = "") -> Dict:
    """Execute a tool by name and return result dictionary."""
    if tool_name == "search_faculty":
        interests = tool_args.get("interests", "")
        regions = tool_args.get("regions", [])
        universities = tool_args.get("universities", "")
        limit = tool_args.get("limit", 10)
        return searcher.search(interests, regions, universities, limit=limit)

    elif tool_name == "scrape_faculty_email":
        homepage = tool_args.get("homepage_url", "")
        email = searcher.get_author_email(homepage)
        return {"success": True, "email": email, "homepage": homepage}

    elif tool_name == "draft_cold_email":
        if not api_key:
            return {"success": False, "error": "OpenRouter API Key required"}
        client = LLMClient(api_key, model or None)
        prof = tool_args.get("professor", {})
        user_info = tool_args.get("user_info", {})
        return client.generate_cold_email(prof, user_info)

    return {"success": False, "error": f"Unknown tool: {tool_name}"}
