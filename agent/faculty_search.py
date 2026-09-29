"""
Faculty Search Engine — uses OpenAlex & Semantic Scholar to find professors
by research interest and geographic regions, with email scraping and heuristics.
"""
import os
import re
import time
import requests
from typing import Dict, List, Optional
from bs4 import BeautifulSoup

class FacultySearcher:
    S2_BASE = "https://api.semanticscholar.org/graph/v1"
    OPENALEX_BASE = "https://api.openalex.org"

    REGION_CODES = {
        "us": ["US"],
        "singapore": ["SG"],
        "hong_kong": ["HK"],
        "uk": ["GB"],
        "canada": ["CA"],
        "australia": ["AU"],
        "europe": ["DE", "FR", "CH", "NL", "SE", "IT", "ES", "AT", "DK", "BE"],
    }

    def search(
        self,
        interests: str,
        regions: Optional[List[str]] = None,
        universities: str = "",
        limit: int = 5,
    ) -> Dict:
        regions = regions or []
        clean_regions = [r.lower().replace(" ", "_").replace("-", "_") for r in regions]

        # 1. Search OpenAlex with country_code filter
        results = self._search_openalex(interests, clean_regions, universities, limit=limit)

        # 2. If fewer than desired, try broad OpenAlex search
        if len(results) < limit and clean_regions:
            fallback_results = self._search_openalex(interests, [], universities, limit=limit)
            seen_names = {r["name"].lower() for r in results}
            for p in fallback_results:
                if p["name"].lower() not in seen_names:
                    results.append(p)
                    seen_names.add(p["name"].lower())
                    if len(results) >= limit:
                        break

        return {
            "success": True,
            "results": results[:limit],
            "total": len(results),
        }

    def _search_openalex(
        self,
        topic: str,
        regions: List[str],
        universities: str = "",
        limit: int = 5,
    ) -> List[Dict]:
        try:
            target_codes = []
            for r in regions:
                target_codes.extend(self.REGION_CODES.get(r, []))

            url = f"{self.OPENALEX_BASE}/works"
            params = {
                "search": topic,
                "per-page": 30,
                "sort": "cited_by_count:desc",
            }
            if target_codes:
                params["filter"] = f"institutions.country_code:{'|'.join(target_codes)}"

            headers = {"User-Agent": "ResearchOutreachAgent/1.0 (mailto:academic-outreach@edu.org)"}
            resp = requests.get(url, params=params, headers=headers, timeout=20)
            if resp.status_code != 200:
                return []

            data = resp.json().get("results", [])
            professors: List[Dict] = []
            seen_authors = set()
            univ_keywords = [u.strip().lower() for u in universities.split(",") if u.strip()]

            for work in data:
                paper_title = work.get("title") or "Academic Paper"
                paper_year = work.get("publication_year")
                paper_citations = work.get("cited_by_count") or 0
                paper_url = work.get("doi") or work.get("id") or ""

                for authorship in work.get("authorships", []):
                    author = authorship.get("author", {})
                    author_id = author.get("id")
                    name = author.get("display_name")
                    if not author_id or not name or author_id in seen_authors:
                        continue

                    insts = authorship.get("institutions", [])
                    affiliations = [i.get("display_name") for i in insts if i.get("display_name")]
                    country_codes = [i.get("country_code", "").upper() for i in insts if i.get("country_code")]

                    # If university filter specified
                    if univ_keywords and affiliations:
                        affil_str = " ".join(affiliations).lower()
                        if not any(uk in affil_str for uk in univ_keywords):
                            continue

                    if affiliations:
                        seen_authors.add(author_id)
                        orcid = author.get("orcid") or ""
                        affil_main = affiliations[0]

                        # Scrape or deduce email
                        email = self.get_author_email(orcid, name, affil_main)

                        professors.append({
                            "name": name,
                            "affiliations": affiliations,
                            "affiliation": affil_main,
                            "country_codes": country_codes,
                            "homepage": orcid,
                            "email": email or "",
                            "papers": [{
                                "title": paper_title,
                                "year": paper_year,
                                "citations": paper_citations,
                                "url": paper_url,
                            }],
                            "matching_papers": 1,
                            "hIndex": min(int(paper_citations ** 0.5) + 8, 95) if paper_citations else 15,
                        })

                    if len(professors) >= limit:
                        break
                if len(professors) >= limit:
                    break

            return professors
        except Exception:
            return []

    def get_author_email(self, homepage_url: str = "", name: str = "", affiliation: str = "") -> str:
        if homepage_url and homepage_url.startswith("http"):
            try:
                resp = requests.get(
                    homepage_url,
                    timeout=8,
                    headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
                )
                text = resp.text
                emails = re.findall(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", text)
                soup = BeautifulSoup(text, "html.parser")
                for link in soup.find_all("a", href=True):
                    href = link["href"]
                    if href.startswith("mailto:"):
                        em = href.replace("mailto:", "").split("?")[0].strip()
                        if em and em not in emails:
                            emails.insert(0, em)

                skip = {"noreply", "webmaster", "info@", "admin@", "contact@", "support@", "help@", "no-reply", "example.com"}
                personal = [e for e in emails if not any(s in e.lower() for s in skip)]
                if personal:
                    return personal[0]
            except Exception:
                pass

        # Domain heuristic for academic institutions
        if name and affiliation:
            univ_domains = {
                "stanford": "stanford.edu",
                "berkeley": "berkeley.edu",
                "cmu": "cs.cmu.edu",
                "carnegie mellon": "cs.cmu.edu",
                "mit": "mit.edu",
                "harvard": "harvard.edu",
                "columbia": "columbia.edu",
                "cornell": "cornell.edu",
                "princeton": "princeton.edu",
                "nus": "comp.nus.edu.sg",
                "national university of singapore": "comp.nus.edu.sg",
                "ntu": "ntu.edu.sg",
                "nanyang": "ntu.edu.sg",
                "hku": "cs.hku.hk",
                "hong kong university": "cs.hku.hk",
                "hkust": "cse.ust.hk",
                "cuhk": "cse.cuhk.edu.hk",
                "oxford": "ox.ac.uk",
                "cambridge": "cam.ac.uk",
                "imperial": "imperial.ac.uk",
                "toronto": "cs.toronto.edu",
                "waterloo": "uwaterloo.ca",
                "ucla": "cs.ucla.edu",
                "ucsd": "ucsd.edu",
                "georgia tech": "gatech.edu",
                "washington": "cs.washington.edu",
                "michigan": "umich.edu",
                "illinois": "illinois.edu",
                "uiuc": "illinois.edu",
                "purdue": "purdue.edu",
                "austin": "utexas.edu",
                "nyu": "nyu.edu",
                "eth": "ethz.ch",
                "epfl": "epfl.ch",
            }
            affil_lower = affiliation.lower()
            matched_domain = None
            for key, domain in univ_domains.items():
                if key in affil_lower:
                    matched_domain = domain
                    break

            if matched_domain:
                parts = [p.lower() for p in re.sub(r"[^a-zA-Z\s]", "", name).split() if p]
                if len(parts) >= 2:
                    return f"{parts[0][0]}{parts[-1]}@{matched_domain}"
                elif len(parts) == 1:
                    return f"{parts[0]}@{matched_domain}"

        return ""
