"""
Core Agent Engine for Research Outreach Agent.
Implements an autonomous reasoning, multi-step planning, tool-executing agent loop with streaming feedback.
"""

import json
import time
from typing import Dict, List, Generator
from agent.tools import execute_tool
from agent.llm_client import LLMClient

class AutonomousOutreachAgent:
    """
    Autonomous AI Agent that:
    1. Receives target research goals and user constraints.
    2. Plans search queries and regional targeting.
    3. Executes search & author aggregation tools.
    4. Autonomously scrapes homepage links to locate professor email addresses.
    5. Evaluates alignment with top papers & generates customized cold emails.
    6. Assembles an Approval Queue for human verification.
    """

    def __init__(self, api_key: str, model: str = "google/gemini-2.0-flash-exp:free"):
        self.api_key = api_key
        self.model = model
        self.llm = LLMClient(api_key, model)

    def run_workflow_stream(
        self,
        interests: str,
        regions: List[str],
        universities: str,
        user_info: Dict,
        max_professors: int = 5
    ) -> Generator[Dict, None, None]:
        """
        Executes the full agent autonomous loop, yielding status events for SSE real-time UI logging.
        """
        yield {
            "type": "thought",
            "step": "Planning Phase",
            "message": f"🤖 Agent initialized with goal: Find up to {max_professors} faculty in [{interests}] within regions {regions}."
        }
        time.sleep(0.5)

        # Step 1: Autonomous Search
        yield {
            "type": "thought",
            "step": "Executing Tool: search_faculty",
            "message": f"🔍 Searching Semantic Scholar graph for top authors matching '{interests}'..."
        }

        search_res = execute_tool(
            "search_faculty",
            {
                "interests": interests,
                "regions": regions,
                "universities": universities,
                "limit": max_professors * 2
            }
        )

        if not search_res.get("success") or not search_res.get("results"):
            yield {
                "type": "error",
                "message": search_res.get("error") or "No faculty matching criteria found."
            }
            return

        profs = search_res["results"]
        yield {
            "type": "thought",
            "step": "Search Completed",
            "message": f"✅ Discovered {len(profs)} potential matching researchers across targeted institutions."
        }
        time.sleep(0.5)

        # Step 2: Scrape emails & Evaluate Alignment
        drafts = []
        for i, prof in enumerate(profs[:max_professors], start=1):
            p_name = prof.get("name", "Unknown Researcher")
            affs = prof.get("affiliations") or ["University"]
            aff_str = ", ".join(affs)
            homepage = prof.get("homepage", "")

            yield {
                "type": "thought",
                "step": f"Processing Candidate {i}/{min(len(profs), max_professors)}",
                "message": f"🎯 Evaluating Prof. {p_name} ({aff_str}) [h-index: {prof.get('hIndex', 'N/A')}]..."
            }

            # Attempt scraping email
            email = None
            if homepage:
                yield {
                    "type": "thought",
                    "step": "Executing Tool: scrape_faculty_email",
                    "message": f"🌐 Scrape web homepage: {homepage}..."
                }
                email_res = execute_tool("scrape_faculty_email", {"homepage_url": homepage})
                if email_res.get("success") and email_res.get("email"):
                    email = email_res["email"]
                    yield {
                        "type": "thought",
                        "step": "Email Found",
                        "message": f"📧 Located email: {email}"
                    }
                else:
                    yield {
                        "type": "thought",
                        "step": "Email Scraping",
                        "message": "⚠️ Could not automatically extract direct email from homepage."
                    }

            # Step 3: LLM Synthesis & Email Drafting
            yield {
                "type": "thought",
                "step": "Executing Tool: draft_cold_email",
                "message": f"✍️ Crafting tailored email linking paper highlights to student profile..."
            }

            email_res = execute_tool(
                "draft_cold_email",
                {"professor": prof, "user_info": user_info},
                api_key=self.api_key,
                model=self.model
            )

            if email_res.get("success"):
                draft_item = {
                    "id": f"draft_{i}",
                    "professor_name": p_name,
                    "affiliation": aff_str,
                    "h_index": prof.get("hIndex", "N/A"),
                    "homepage": homepage,
                    "email": email or "",
                    "papers": prof.get("papers", []),
                    "subject": email_res.get("subject", "Research Position Inquiry"),
                    "body": email_res.get("body", "")
                }
                drafts.append(draft_item)
                yield {
                    "type": "draft_created",
                    "draft": draft_item,
                    "message": f"✨ Created customized cold email draft for Prof. {p_name}!"
                }
            else:
                yield {
                    "type": "thought",
                    "step": "Draft Error",
                    "message": f"❌ Failed to draft email for {p_name}: {email_res.get('error')}"
                }
            time.sleep(0.3)

        # Step 4: Finalize Queue for Approval
        yield {
            "type": "complete",
            "message": f"🎉 Agent workflow finished! Prepared {len(drafts)} drafts for human review.",
            "total_drafts": len(drafts)
        }
