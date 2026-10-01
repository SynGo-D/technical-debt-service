from types import SimpleNamespace

from src.agents.llm_client import LLMError
from src.agents.classification_agent import ClassificationAgent
from src.agents.estimation_agent import EstimationAgent
from src.agents.rule_matching_agent import RuleMatchingAgent, shortlist
from src.domain.debt import DebtCalculationRequest
from src.domain.finding import AnalysisFinding
from src.infrastructure.sonar_client import parse_effort, rule_from_api
from src.services.aggregator import DebtAggregator
from src.services.cost_calculator import CostCalculator
from src.services.debt_service import DebtService
from src.services.health_calculator import HealthCalculator
from src.services.sonar_assessor import SonarDebtAssessor, assessment_from_rule


def rule(key, name, severity="MAJOR", rule_type="CODE_SMELL", minutes=5, language="js"):
    return SimpleNamespace(
        key=key, name=name, language=language, rule_type=rule_type,
        severity=severity, remediation_minutes=minutes,
    )


UNUSED = rule("javascript:S1481", "Unused local variables and functions should be removed", "MINOR", minutes=5)
EVAL = rule("javascript:S1523", "Dynamically executing code is security-sensitive", "CRITICAL", "SECURITY_HOTSPOT", None)
EMPTY = rule("javascript:S108", "Nested blocks of code should not be left empty", "MAJOR", minutes=5)


def finding(i=1, rule_id="no-unused-vars", message="'x' is assigned a value but never used. Unused variable.",
            severity="warning", category="unused_code") -> AnalysisFinding:
    return AnalysisFinding(
        finding_id=f"00000000-0000-0000-0000-00000000000{i}",
        repository="o/r", pull_request_number=1, commit_sha="abc",
        file_path="src/a.js", line=10, severity=severity, category=category,
        rule_id=rule_id, message=message, tool="eslint", fingerprint="f" * 64,
    )


class ScriptedLLM:
    def __init__(self, *replies):
        self.replies = list(replies)
        self.calls = 0

    async def generate(self, system_prompt, user_prompt):
        self.calls += 1
        r = self.replies.pop(0) if len(self.replies) > 1 else self.replies[0]
        if isinstance(r, Exception):
            raise r
        return r


class FakeCatalog:
    """In-memory stand-in for RuleCatalogRepository."""

    def __init__(self, rules):
        self.rules = {r.key: r for r in rules}
        self.mappings = {}

    async def status(self):
        return {"rules": len(self.rules)}

    async def rules_for_languages(self, languages):
        return [r for r in self.rules.values() if r.language in languages]

    async def get_rule(self, key):
        return self.rules.get(key)

    async def get_mapping(self, tool, rule_id):
        if (tool, rule_id) in self.mappings:
            return SimpleNamespace(sonar_rule_key=self.mappings[(tool, rule_id)])
        return None

    async def save_mapping(self, tool, rule_id, sonar_rule_key):
        self.mappings.setdefault((tool, rule_id), sonar_rule_key)


def assessor(llm, rules=(UNUSED, EVAL, EMPTY)):
    catalog = FakeCatalog(rules)
    return SonarDebtAssessor(catalog, RuleMatchingAgent(llm)), catalog


# ---- reading SonarQube's API -----------------------------------------------

def test_parse_effort():
    assert [parse_effort(v) for v in ("5min", "1h", "1h30min", "1d", "", None)] == [5, 60, 90, 480, None, None]


def test_rule_from_api():
    assert rule_from_api({
        "key": "javascript:S1481", "name": "Unused vars", "lang": "js",
        "type": "CODE_SMELL", "severity": "MINOR", "remFnBaseEffort": "5min",
        "sysTags": ["unused"],
        "descriptionSections": [{"key": "root_cause", "content": "<p>Dead   <code>store</code></p>"}],
    }) == {
        "key": "javascript:S1481", "name": "Unused vars", "language": "js",
        "rule_type": "CODE_SMELL", "severity": "MINOR", "remediation_minutes": 5,
        "search_text": "unused Dead store",
    }
    assert rule_from_api({"name": "no key"}) is None


def test_shortlist_also_searches_the_description():
    by_description = rule("javascript:S1523", "Dynamic code execution should not use user-controlled data")
    by_description.search_text = "cwe APIs such as eval execute code provided as strings"
    f = finding(rule_id="no-eval", message="eval can be harmful.")
    assert shortlist(f, [UNUSED, EMPTY]) == []                  # names alone share nothing
    assert shortlist(f, [UNUSED, by_description]) == [by_description]


# ---- values come from the catalog row --------------------------------------

def test_values_are_read_from_the_rule():
    assert assessment_from_rule(UNUSED) | {"recommendation": ""} == {
        "debt_type": "MAINTAINABILITY", "impact": "LOW", "risk": "LOW", "complexity": "MEDIUM",
        "estimated_minutes": 5, "confidence": 1.0, "recommendation": "",
    }
    hotspot = assessment_from_rule(EVAL)  # no effort in SonarQube -> default by severity
    assert (hotspot["debt_type"], hotspot["risk"], hotspot["estimated_minutes"]) == ("SECURITY", "HIGH", 60)


# ---- matching --------------------------------------------------------------

def test_shortlist_ranks_by_shared_words_and_is_stable():
    rules = [EMPTY, EVAL, UNUSED]
    first = shortlist(finding(), rules)
    assert first[0] is UNUSED
    assert first == shortlist(finding(), list(reversed(rules)))


async def test_agent_cannot_invent_a_rule():
    agent = RuleMatchingAgent(ScriptedLLM('{"sonar_rule_key": "javascript:S9999", "reason": "x"}'))
    assert await agent.match(finding(), [UNUSED, EMPTY]) is None


async def test_mapping_is_decided_once_and_reused():
    llm = ScriptedLLM('{"sonar_rule_key": "javascript:S1481", "reason": "same check"}')
    a, catalog = assessor(llm)

    await a.prepare()
    first = await a.assess(finding(1))
    second = await a.assess(finding(2))  # same linter rule, same run
    assert first == second and first["estimated_minutes"] == 5
    assert llm.calls == 1

    await a.prepare()                    # a later run
    assert await a.assess(finding(3)) == first
    assert llm.calls == 1                # answered from the stored mapping
    assert catalog.mappings == {("eslint", "no-unused-vars"): "javascript:S1481"}


async def test_no_equivalent_rule_is_remembered_as_unmapped():
    llm = ScriptedLLM('{"sonar_rule_key": null, "reason": "nothing matches"}')
    a, catalog = assessor(llm)
    await a.prepare()
    assert await a.assess(finding()) is None
    assert catalog.mappings == {("eslint", "no-unused-vars"): None}


async def test_llm_outage_is_not_stored():
    a, catalog = assessor(ScriptedLLM(LLMError("down")))
    await a.prepare()
    assert await a.assess(finding()) is None
    assert catalog.mappings == {}        # asked again next run


# ---- service ---------------------------------------------------------------

def service(llm, a):
    return DebtService(
        ClassificationAgent(llm), EstimationAgent(llm), DebtAggregator(),
        CostCalculator(25), HealthCalculator(), assessor=a,
    )


def request(*findings):
    return DebtCalculationRequest(
        repository="o/r", pull_request_number=1, commit_sha="abc", findings=list(findings),
    )


async def test_service_uses_catalog_values():
    # Replies in processing order: the service takes the most severe finding first.
    llm = ScriptedLLM(
        '{"sonar_rule_key": null, "reason": ""}',                 # custom/unused-thing (error)
        '{"sonar_rule_key": "javascript:S1481", "reason": ""}',   # no-unused-vars (warning)
    )
    a, _ = assessor(llm)
    out = await service(llm, a).calculate(request(
        finding(1),
        finding(2, rule_id="custom/unused-thing", message="unused code block", severity="error", category="bug"),
    ))

    assert out["method"] == "sonarqube" and out["unmapped_issues"] == 1
    by_rule = {i["rule_id"]: i for i in out["issues"]}
    assert (by_rule["no-unused-vars"]["source"], by_rule["no-unused-vars"]["estimated_minutes"]) == ("sonarqube", 5)
    # unmapped: fixed default from the linter's severity, not a model estimate
    assert (by_rule["custom/unused-thing"]["source"], by_rule["custom/unused-thing"]["risk"]) == ("default", "HIGH")
    assert llm.calls == 2                # matching only - no classify/estimate calls


async def test_service_falls_back_to_llm_while_catalog_is_empty():
    llm = ScriptedLLM(LLMError("down"))
    a, _ = assessor(llm, rules=())
    out = await service(llm, a).calculate(request(finding()))
    assert out["method"] == "llm" and out["issues"][0]["source"] == "llm"
