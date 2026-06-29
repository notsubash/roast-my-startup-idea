"""Controlled Tavily web research for factual startup context."""

from dataclasses import dataclass
import json
import re
from urllib import request
from urllib.error import HTTPError, URLError

from jinja2 import Environment, FileSystemLoader
from pydantic import BaseModel, Field

from config import PROMPTS_DIR
from idea_context import wrap_user_idea

template_env = Environment(loader=FileSystemLoader(PROMPTS_DIR))


@dataclass(frozen=True)
class ResearchFinding:
    title: str
    url: str
    content: str


@dataclass(frozen=True)
class ResearchContext:
    query: str
    findings: list[ResearchFinding]


class WebSearchDecision(BaseModel):
    use_search: bool = Field(description="Whether web search is required for factual validation.")
    rationale: str = Field(
        description="Short reason for decision; mention factual risk if searching."
    )
    query: str | None = Field(
        default=None,
        description="A single high-signal Tavily query when use_search is true.",
    )


class TavilyHttpClient:
    """Tiny Tavily client via HTTP; avoids SDK lock-in."""

    def __init__(self, api_key: str):
        self.api_key = api_key

    def search(self, query: str, max_results: int) -> list[dict]:
        payload = json.dumps(
            {
                "api_key": self.api_key,
                "query": query,
                "max_results": max_results,
                "search_depth": "basic",
                "include_raw_content": False,
            }
        ).encode("utf-8")
        req = request.Request(
            url="https://api.tavily.com/search",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=15) as resp:
                body = resp.read().decode("utf-8")
        except HTTPError as exc:
            if exc.code == 401:
                # ponytail: invalid/expired key — skip research instead of failing the roast run.
                return []
            raise RuntimeError(f"Tavily search failed: {exc}") from exc
        except URLError as exc:
            raise RuntimeError(f"Tavily search failed: {exc}") from exc

        parsed = json.loads(body)
        return parsed.get("results", [])


def decide_web_search_usage(policy_model, startup_idea: str) -> WebSearchDecision:
    """Prompt-based policy gate for sparing web search usage."""
    wrapped_idea = wrap_user_idea(startup_idea)
    decision_prompt = template_env.get_template("web_search_policy_prompt.jinja2").render(
        startup_idea=wrapped_idea,
    )
    try:
        structured_model = policy_model.with_structured_output(WebSearchDecision)
        decision = structured_model.invoke(decision_prompt)
    except Exception:
        fallback_prompt = template_env.get_template(
            "web_search_policy_fallback_prompt.jinja2"
        ).render(policy_prompt=decision_prompt)
        response = policy_model.invoke(fallback_prompt)
        content = getattr(response, "content", response)
        if not isinstance(content, str):
            content = str(content)
        data = _parse_json_object(content)
        if data is None:
            return WebSearchDecision(
                use_search=False,
                rationale="Policy evaluation unavailable; skipping web search.",
                query=None,
            )
        try:
            decision = WebSearchDecision.model_validate(data)
        except Exception:
            return WebSearchDecision(
                use_search=False,
                rationale="Policy output invalid; skipping web search.",
                query=None,
            )

    if decision.use_search and not (decision.query or "").strip():
        fallback_query = template_env.get_template("research_query_prompt.jinja2").render(
            startup_idea=wrapped_idea,
        )
        return WebSearchDecision(
            use_search=True,
            rationale=decision.rationale,
            query=fallback_query.strip(),
        )
    return decision


def _parse_json_object(content: str) -> dict | None:
    raw = content.strip()
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{[\s\S]*\}", raw)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    return data


def _build_search_query(startup_idea: str) -> str:
    return (
        template_env.get_template("research_query_prompt.jinja2")
        .render(
            startup_idea=wrap_user_idea(startup_idea),
        )
        .strip()
    )


def _normalize_findings(raw_results: list[dict]) -> list[ResearchFinding]:
    findings: list[ResearchFinding] = []
    for row in raw_results:
        title = str(row.get("title") or "Untitled source").strip()
        url = str(row.get("url") or "").strip()
        content = str(row.get("content") or "").strip()
        if not url:
            continue
        findings.append(
            ResearchFinding(
                title=title,
                url=url,
                content=content,
            )
        )
    return findings


def build_research_context(
    startup_idea: str,
    tavily_client,
    max_results: int,
    enabled: bool,
    policy_model=None,
    decision: WebSearchDecision | None = None,
    force: bool = False,
) -> ResearchContext | None:
    """Run one bounded search pass and return normalized findings."""
    if not enabled:
        return None
    if force:
        query = _build_search_query(startup_idea)
    elif decision is not None:
        if not decision.use_search:
            return None
        query = (decision.query or "").strip() or _build_search_query(startup_idea)
    else:
        if policy_model is None:
            return None
        decision = decide_web_search_usage(policy_model, startup_idea)
        if not decision.use_search:
            return None
        query = (decision.query or "").strip() or _build_search_query(startup_idea)

    raw_results = tavily_client.search(query=query, max_results=max_results)
    findings = _normalize_findings(raw_results)
    if not findings:
        return None
    return ResearchContext(query=query, findings=findings[:max_results])


def research_context_payload(context: ResearchContext) -> dict:
    """Frontend-safe research payload for SSE / REST."""
    return {
        "query": context.query,
        "findings": [
            {
                "title": finding.title,
                "url": finding.url,
                "snippet": finding.content[:260].strip(),
            }
            for finding in context.findings
        ],
    }


def format_research_context(context: ResearchContext) -> str:
    """Render compact cited research block for prompts."""
    prepared_findings = [
        {
            "title": finding.title,
            "url": finding.url,
            "snippet": finding.content[:260].strip(),
        }
        for finding in context.findings
    ]
    return (
        template_env.get_template("research_context_prompt.jinja2")
        .render(
            query=context.query,
            findings=prepared_findings,
        )
        .strip()
    )


def make_deepagent_search_tool(tavily_client, max_results: int):
    """Return a callable tool for DeepAgents orchestrator."""

    def tavily_search(query: str) -> str:
        """Search the public web for current factual signals.

        Use this only when a claim depends on current external facts
        (competition, pricing, regulation, trend, adoption, or market sizing).
        """

        results = tavily_client.search(query=query, max_results=max_results)
        findings = _normalize_findings(results)[:max_results]
        if not findings:
            return "No web results found."
        context = ResearchContext(query=query, findings=findings)
        return format_research_context(context)

    return tavily_search
