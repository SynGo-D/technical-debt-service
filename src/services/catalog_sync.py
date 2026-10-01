import asyncio
import logging
from datetime import datetime, timedelta, timezone

from ..infrastructure.sonar_client import SonarClient, SonarError

logger = logging.getLogger(__name__)

# How often the background loop checks whether a sync is due.
_CHECK_EVERY_SECONDS = 3600


class CatalogSync:
    """Copies SonarQube's rule definitions into the local sonar_rules table.

    This is the only place SonarQube is contacted. Pull-request calculations
    read the local table, so they are unaffected by SonarQube being slow or
    down - they just keep using the last synced copy.
    """

    def __init__(self, catalog, sonar_url: str, sonar_token: str, languages: str, interval_hours: int):
        self.catalog = catalog
        self.sonar_url = sonar_url
        self.sonar_token = sonar_token
        self.languages = languages
        self.interval = timedelta(hours=interval_hours)
        self._lock = asyncio.Lock()

    async def sync(self) -> int:
        """Fetch every rule and upsert it. Returns the number of rules."""
        async with self._lock:
            client = SonarClient(self.sonar_url, self.sonar_token)

            try:
                rules = await client.fetch_rules(self.languages)
            finally:
                await client.aclose()

            count = await self.catalog.replace_rules(rules)

            logger.info("SonarQube rule catalog synced: %d rules", count)

            return count

    async def is_due(self) -> bool:
        last = await self.catalog.last_synced_at()
        return last is None or datetime.now(timezone.utc) - last >= self.interval

    async def run_forever(self) -> None:
        """Background task: sync when the catalog is older than the interval
        (weekly by default). A failed sync is retried at the next check."""
        while True:
            try:
                if await self.is_due():
                    await self.sync()
            except SonarError as e:
                logger.warning("SonarQube rule catalog sync failed: %s", e)
            except Exception:
                logger.exception("SonarQube rule catalog sync failed")

            await asyncio.sleep(_CHECK_EVERY_SECONDS)
