import re

from ..domain.finding import AnalysisFinding
from .base import BaseAgent


SYSTEM_PROMPT = """
You match a static-analysis finding to the SonarQube rule that checks the
same thing.

You are given one finding and a numbered list of candidate SonarQube rules.
Choose the candidate that detects the same problem as the finding.

Return ONLY valid JSON:

{
  "sonar_rule_key": "<key copied exactly from the candidates, or null>",
  "reason": "..."
}

Rules:
- The key MUST be copied exactly from the candidate list.
- Use null when no candidate checks the same problem. Do not pick a loosely
  related rule just to give an answer.
"""

SHORTLIST_SIZE = 30

_NAME_WEIGHT = 3

_STOPWORDS = {
    "the", "and", "for", "not", "should", "be", "are", "is", "of", "to", "in",
    "a", "an", "with", "use", "used", "using", "no", "or", "on", "that", "this",
    "it", "its", "as", "by", "from", "at", "must", "can", "has", "have",
}


def tokens(text: str) -> set[str]:
    # camelCase / kebab-case / snake_case rule ids split into words too.
    text = re.sub(r"([a-z])([A-Z])", r"\1 \2", text)
    words = (w if len(w) < 4 else w.rstrip("s") for w in re.findall(r"[a-z]+", text.lower()))
    return {w for w in words if len(w) > 2 and w not in _STOPWORDS}


def languages_for(finding: AnalysisFinding) -> list[str]:
    """SonarQube language keys to search, from the finding's file type."""
    path = finding.file_path.lower()

    if path.endswith(".py"):
        return ["py"]
    if path.endswith((".ts", ".tsx")):
        return ["ts", "js"]
    return ["js", "ts"]


def shortlist(finding: AnalysisFinding, rules: list, size: int = SHORTLIST_SIZE) -> list:
    """The catalog rules that share the most words with the finding. A word
    in the rule's name counts three times a word in its description.
    Plain word overlap: the same finding always gets the same shortlist."""
    wanted = tokens(f"{finding.rule_id} {finding.message}")

    scored = [
        (
            _NAME_WEIGHT * len(wanted & tokens(rule.name))
            + len(wanted & tokens(getattr(rule, "search_text", None) or "")),
            rule,
        )
        for rule in rules
    ]

    ranked = sorted(
        (item for item in scored if item[0] > 0),
        key=lambda item: (-item[0], item[1].key),
    )

    return [rule for _, rule in ranked[:size]]


class RuleMatchingAgent(BaseAgent):
    """Picks the SonarQube rule equivalent to a linter rule. It only selects
    from the catalog - every debt value comes from the chosen rule's row."""

    async def match(self, finding: AnalysisFinding, candidates: list) -> str | None:
        """The chosen candidate's key, or None when nothing is equivalent.
        Raises AgentError when the LLM is unavailable."""

        listing = "\n".join(
            f"{n}. {rule.key} — {rule.name}" for n, rule in enumerate(candidates, 1)
        )

        user_prompt = f"""
Finding:

Tool: {finding.tool}
Rule: {finding.rule_id}
Category: {finding.category}
Message: {finding.message}
CWE: {finding.metadata.get("cwe", "n/a")}

Candidate SonarQube rules:

{listing}
"""

        data = await self.ask_json(SYSTEM_PROMPT, user_prompt)

        key = str(data.get("sonar_rule_key") or "").strip()

        # Anything not in the shortlist (an invented key included) is "no match".
        return key if key in {rule.key for rule in candidates} else None
