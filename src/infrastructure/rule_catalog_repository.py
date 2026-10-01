from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from .models import RuleMapping, SonarRule


class RuleCatalogRepository:
    """sonar_rules (the local copy of SonarQube's rules) and rule_mappings
    (linter rule -> SonarQube rule), in this service's own database."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]):
        self._sf = session_factory

    # ---- catalog -----------------------------------------------------------

    async def replace_rules(self, rules: list[dict]) -> int:
        """Upsert the rules fetched from SonarQube; returns how many."""

        if not rules:
            return 0

        async with self._sf() as session, session.begin():

            # asyncpg caps a statement at 32767 parameters.
            for start in range(0, len(rules), 1000):
                statement = insert(SonarRule).values(rules[start:start + 1000])

                await session.execute(
                    statement.on_conflict_do_update(
                        index_elements=[SonarRule.key],
                        set_={
                            "name": statement.excluded.name,
                            "language": statement.excluded.language,
                            "rule_type": statement.excluded.rule_type,
                            "severity": statement.excluded.severity,
                            "remediation_minutes": statement.excluded.remediation_minutes,
                            "search_text": statement.excluded.search_text,
                            "synced_at": func.now(),
                        },
                    )
                )

        return len(rules)

    async def status(self) -> dict:
        async with self._sf() as session:
            count, last = (
                await session.execute(
                    select(func.count(SonarRule.key), func.max(SonarRule.synced_at))
                )
            ).one()

            mappings = (
                await session.execute(select(func.count()).select_from(RuleMapping))
            ).scalar_one()

        return {
            "rules": count,
            "last_synced_at": last.isoformat() if last else None,
            "mapped_linter_rules": mappings,
        }

    async def last_synced_at(self) -> datetime | None:
        async with self._sf() as session:
            return (
                await session.execute(select(func.max(SonarRule.synced_at)))
            ).scalar_one()

    async def rules_for_languages(self, languages: list[str]) -> list[SonarRule]:
        async with self._sf() as session:
            return list(
                (
                    await session.execute(
                        select(SonarRule).where(SonarRule.language.in_(languages))
                    )
                ).scalars()
            )

    async def get_rule(self, key: str) -> SonarRule | None:
        async with self._sf() as session:
            return await session.get(SonarRule, key)

    # ---- mappings ----------------------------------------------------------

    async def get_mapping(self, tool: str, rule_id: str) -> RuleMapping | None:
        async with self._sf() as session:
            return await session.get(RuleMapping, (tool, rule_id))

    async def save_mapping(self, tool: str, rule_id: str, sonar_rule_key: str | None) -> None:
        async with self._sf() as session, session.begin():
            await session.execute(
                insert(RuleMapping)
                .values(tool=tool, rule_id=rule_id, sonar_rule_key=sonar_rule_key)
                .on_conflict_do_nothing()
            )
