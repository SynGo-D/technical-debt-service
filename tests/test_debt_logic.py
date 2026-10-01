import pytest

from src.agents.base import AgentError, parse_json_object
from src.agents.classification_agent import ClassificationAgent
from src.agents.estimation_agent import EstimationAgent
from src.agents.llm_client import LLMError
from src.config import Settings
from src.domain.agent_outputs import ClassificationOutput
from src.domain.debt import DebtCalculationRequest
from src.domain.finding import AnalysisFinding
from src.infrastructure.analysis_repository import introduced_findings
from src.services.aggregator import DebtAggregator
from src.services.cost_calculator import CostCalculator
from src.services.debt_service import DebtService
from src.services.health_calculator import HealthCalculator


def finding(i=1, severity="error", category="vulnerability", **kw) -> AnalysisFinding:
    return AnalysisFinding(
        finding_id=f"00000000-0000-0000-0000-00000000000{i}",
        repository="o/r", pull_request_number=1, commit_sha="abc",
        file_path="src/a.js", line=10, severity=severity, category=category,
        rule_id="security/eval", message="m", tool="eslint", fingerprint="f" * 64,
        **kw,
    )


class ScriptedLLM:
    """Stands in for LLMClient: replays replies; the last one repeats."""

    def __init__(self, *replies):
        self.replies = list(replies)
        self.calls = 0

    async def generate(self, system_prompt, user_prompt):
        self.calls += 1
        r = self.replies.pop(0) if len(self.replies) > 1 else self.replies[0]
        if isinstance(r, Exception):
            raise r
        return r


def service(llm, **kw) -> DebtService:
    return DebtService(
        ClassificationAgent(llm), EstimationAgent(llm), DebtAggregator(),
        CostCalculator(25), HealthCalculator(), **kw,
    )


# ---- calculators -----------------------------------------------------------

@pytest.mark.parametrize(
    "findings,crit,high,hours,lines,score,status",
    [
        (1, 1, 0, 2.00, 200, 73, "GOOD"),     # ratio 0.6 -> -10
        (3, 0, 1, 6.25, 300, 76, "GOOD"),     # ratio 1.25 -> -10
        (5, 0, 2, 3.00, 0, 74, "GOOD"),       # no diff -> no ratio penalty
    ],
)
def test_health_score(findings, crit, high, hours, lines, score, status):
    h = HealthCalculator()
    got = h.calculate(findings, crit, high, hours, lines)
    assert got == score
    assert h.status(got) == status


def test_cost():
    assert CostCalculator(25).calculate(375) == 156.25


# ---- agents ----------------------------------------------------------------

def test_parse_json_variants():
    assert parse_json_object('```json\n{"a": 1}\n```') == {"a": 1}
    assert parse_json_object('Sure! {"a": 1} hope that helps') == {"a": 1}
    with pytest.raises(AgentError):
        parse_json_object("no json here")


async def test_classification_normalizes_bad_values():
    llm = ScriptedLLM(
        '{"debt_type":"security","impact":"severe","risk":"critical",'
        '"complexity":"low","confidence":7,"reason":"x"}'
    )
    out = await ClassificationAgent(llm).classify(finding())
    assert out.debt_type == "SECURITY"   # case-normalised
    assert out.impact == "HIGH"          # invalid -> derived from severity=error
    assert out.risk == "CRITICAL"
    assert out.confidence == 1.0         # clamped


async def test_classification_falls_back_when_llm_down():
    llm = ScriptedLLM(LLMError("boom"))
    out = await ClassificationAgent(llm).classify(finding(category="bug", severity="warning"))
    assert (out.debt_type, out.risk) == ("BUG", "MEDIUM")
    assert llm.calls == 2  # retried once


async def test_estimation_clamps_and_falls_back():
    c = ClassificationOutput(
        debt_type="BUG", impact="LOW", risk="LOW",
        complexity="LOW", confidence=1, reason="",
    )
    big = await EstimationAgent(ScriptedLLM(
        '{"estimated_minutes": 999999, "confidence": 0.9, "recommendation": "r", "reasoning": "x"}'
    )).estimate(finding(), c)
    assert big.estimated_minutes == 2400

    fb = await EstimationAgent(ScriptedLLM('{"oops": true}')).estimate(
        finding(remediation_minutes=45), c
    )
    assert fb.estimated_minutes == 45


# ---- service ---------------------------------------------------------------

async def test_service_caps_sorts_and_summarises():
    svc = service(ScriptedLLM(LLMError("down")), concurrency=3, max_findings=2)
    out = await svc.calculate(DebtCalculationRequest(
        repository="o/r", pull_request_number=1, commit_sha="abc",
        findings=[finding(1, "info", "style"), finding(2, "error"), finding(3, "warning", "bug")],
        lines_added=100, lines_removed=100,
    ))

    assert out["findings_received"] == 3 and out["findings_skipped"] == 1
    # max_findings=2 keeps the most severe: error + warning, drops info
    assert {str(i["finding_id"])[-1] for i in out["issues"]} == {"2", "3"}

    s = out["summary"]
    assert s["total_findings"] == 2 and s["security_issues"] == 1 and s["bugs"] == 1
    assert s["debt_ratio"] == round(s["total_debt_minutes"] / 200, 4)
    assert out["issues"][0]["risk"] == "HIGH"  # sorted riskiest first


async def test_ratio_none_without_diff():
    out = await service(ScriptedLLM(LLMError("down"))).calculate(DebtCalculationRequest(
        repository="o/r", pull_request_number=1, commit_sha="a", findings=[finding()],
    ))
    assert out["summary"]["debt_ratio"] is None


# ---- PR scope --------------------------------------------------------------

def test_only_findings_on_changed_lines_are_charged():
    new = finding(1, metadata={"on_changed_line": True})
    old = finding(2, metadata={"on_changed_line": False})
    kept, scope = introduced_findings([new, old], changes_available=True)
    assert kept == [new] and scope == "pull_request"


def test_all_findings_counted_when_diff_unavailable():
    fs = [finding(1, metadata={"on_changed_line": True}), finding(2, metadata={"on_changed_line": False})]
    kept, scope = introduced_findings(fs, changes_available=False)
    assert kept == fs and scope == "repository"


def test_all_findings_counted_when_untagged():
    fs = [finding(1), finding(2)]  # older analysis-engine: no on_changed_line tag
    kept, scope = introduced_findings(fs, changes_available=True)
    assert kept == fs and scope == "repository"


# ---- config ----------------------------------------------------------------

def test_plain_postgres_url_is_upgraded_to_asyncpg():
    s = Settings(
        _env_file=None,
        database_url="postgresql://a:b@h:5432/d",
        analysis_database_url="postgres://a:b@h:5434/e",
    )
    assert s.database_url.startswith("postgresql+asyncpg://")
    assert s.analysis_database_url == "postgresql+asyncpg://a:b@h:5434/e"


def test_analysis_db_defaults_to_analysis_engine_compose():
    s = Settings(_env_file=None)
    assert s.analysis_database_url.endswith("localhost:5434/analysis_engine_db")


class TestSummaryScopeIsConsistent:
    """
    Every headline in the repository summary must count the same thing.

    A change once made total_debt_minutes mean "the latest pull request"
    while estimated_cost, total_findings and by_type still meant "all of
    them". Nothing raised, nothing failed, and the dashboard showed 6.75
    hours costing $543.75 — an $80/hour developer on a $25/hour rate.
    These assert the arithmetic that would have caught it.
    """

    @staticmethod
    def _summary(reviews: list[dict]) -> dict:
        """The aggregation repository_summary performs, over plain dicts."""
        total_minutes = sum(r["total_debt_minutes"] for r in reviews)
        newest = reviews[0]
        return {
            "total_debt_minutes": total_minutes,
            "total_debt_hours": round(total_minutes / 60, 2),
            "estimated_cost": float(sum(r["estimated_cost"] for r in reviews)),
            "total_findings": sum(r["total_findings"] for r in reviews),
            "latest_pull_request": {
                "pull_request_number": newest["pull_request_number"],
                "total_debt_minutes": newest["total_debt_minutes"],
                "total_debt_hours": round(newest["total_debt_minutes"] / 60, 2),
                "estimated_cost": float(newest["estimated_cost"]),
            },
        }

    @staticmethod
    def _reviews() -> list[dict]:
        # Newest first, as the query orders them. At $25/hour.
        return [
            {"pull_request_number": 1, "total_debt_minutes": 405, "estimated_cost": 168.75, "total_findings": 12},
            {"pull_request_number": 2, "total_debt_minutes": 900, "estimated_cost": 375.00, "total_findings": 20},
        ]

    def test_cost_and_hours_imply_the_configured_rate(self):
        s = self._summary(self._reviews())

        # The check that would have failed: if one of these counts every
        # pull request and the other counts one, the implied rate is wrong.
        assert s["estimated_cost"] / s["total_debt_hours"] == pytest.approx(25.0)

    def test_the_total_is_every_pull_request_not_just_the_newest(self):
        s = self._summary(self._reviews())

        assert s["total_debt_minutes"] == 405 + 900
        assert s["total_findings"] == 12 + 20

    def test_the_newest_pull_request_is_reported_separately(self):
        s = self._summary(self._reviews())
        latest = s["latest_pull_request"]

        # Idusha's intent, kept — the figure is available without the
        # repository total having to mean something narrower than it says.
        assert latest["pull_request_number"] == 1
        assert latest["total_debt_minutes"] == 405
        assert latest["total_debt_hours"] == 6.75
        assert latest["estimated_cost"] / latest["total_debt_hours"] == pytest.approx(25.0)

    def test_a_single_pull_request_makes_the_two_agree(self):
        s = self._summary(self._reviews()[:1])

        # With one pull request the distinction is invisible, which is why
        # the original change looked correct when it was made.
        assert s["total_debt_minutes"] == s["latest_pull_request"]["total_debt_minutes"]
