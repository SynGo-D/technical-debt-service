"""Reads rule definitions from SonarQube's Web API.

Used only by the catalog sync (services/catalog_sync.py). Nothing on the
pull-request calculation path imports this module.
"""
import re

import httpx


class SonarError(RuntimeError):
    pass


_EFFORT_PART = re.compile(r"(\d+) ?(d|h|min)")

_MINUTES_PER = {"d": 8 * 60, "h": 60, "min": 1}  # SonarQube's day is 8 hours


def parse_effort(value: str | None) -> int | None:
    """'5min' -> 5, '1h' -> 60, '1h30min' -> 90, '1d' -> 480, '' -> None"""
    if not value:
        return None

    parts = _EFFORT_PART.findall(value)

    if not parts:
        return None

    return sum(int(amount) * _MINUTES_PER[unit] for amount, unit in parts)


def rule_from_api(raw: dict) -> dict | None:
    """One rule from api/rules/search, in the shape of the sonar_rules table."""
    key, language = raw.get("key"), raw.get("lang")

    if not key or not language:
        return None

    # Constant rules carry a base effort; linear ones only an effort per
    # unit of "gap", which is the least one occurrence costs.
    minutes = parse_effort(raw.get("remFnBaseEffort")) or parse_effort(
        raw.get("remFnGapMultiplier")
    )

    return {
        "key": key,
        "name": raw.get("name") or key,
        "language": language,
        "rule_type": raw.get("type") or "CODE_SMELL",
        "severity": raw.get("severity") or "MAJOR",
        "remediation_minutes": minutes,
        "search_text": _search_text(raw),
    }


_HTML_TAG = re.compile(r"<[^>]+>")

_SEARCH_TEXT_LIMIT = 6000


def _search_text(raw: dict) -> str:
    """Tags plus the rule's description as plain text - what a finding is
    compared against when looking for its equivalent rule. A rule's name
    alone often shares no words with a linter's message ("eval can be
    harmful" vs "Dynamic code execution should not use user-controlled data")."""
    description = raw.get("htmlDesc") or " ".join(
        section.get("content", "") for section in raw.get("descriptionSections", [])
    )

    parts = [*raw.get("sysTags", []), *raw.get("tags", []), _HTML_TAG.sub(" ", description)]

    return " ".join(" ".join(parts).split())[:_SEARCH_TEXT_LIMIT]


class SonarClient:

    PAGE_SIZE = 500

    def __init__(self, base_url: str, token: str = "", timeout: float = 60.0):
        self._http = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            # A SonarQube token is sent as the basic-auth user name.
            auth=(token, "") if token else None,
            timeout=timeout,
        )

    async def fetch_rules(self, languages: str) -> list[dict]:
        rules: list[dict] = []
        page = 1

        try:
            while True:
                response = await self._http.get(
                    "/api/rules/search",
                    params={"languages": languages, "ps": self.PAGE_SIZE, "p": page},
                )
                response.raise_for_status()
                data = response.json()

                batch = data.get("rules", [])
                rules.extend(r for r in map(rule_from_api, batch) if r)

                total = data.get("total") or data.get("paging", {}).get("total", 0)

                if not batch or page * self.PAGE_SIZE >= total:
                    return rules

                page += 1

        except httpx.HTTPStatusError as e:
            raise SonarError(
                f"SonarQube returned HTTP {e.response.status_code}: {e.response.text[:200]}"
            ) from e

        except (httpx.HTTPError, ValueError) as e:
            raise SonarError(f"SonarQube request failed: {e!r}") from e

    async def aclose(self) -> None:
        await self._http.aclose()
