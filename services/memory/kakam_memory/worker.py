import asyncio
import logging

from .config import Settings
from .repository import Repository

log = logging.getLogger(__name__)


async def run():
    cfg = Settings()
    cfg.validate()
    repo = Repository(cfg.database_url)
    await asyncio.to_thread(repo.migrate)
    ticks = 0
    while True:
        try:
            if ticks % 300 == 0:
                await asyncio.to_thread(repo.cleanup)
            ticks += 1
            job = await asyncio.to_thread(repo.claim)
            if not job:
                await asyncio.sleep(2)
                continue
            success = False
            try:
                async with asyncio.timeout(450):
                    # v2 write authority comes only from manual actions/confirmed proposals.
                    # Retain the worker for cleanup; legacy unapproved jobs must not write.
                    pass
                success = True
            except Exception as exc:
                log.warning('Memory job failed (%s); retry is bounded', type(exc).__name__)
            await asyncio.to_thread(repo.finish, job, success)
        except Exception as exc:
            log.warning('Memory worker unavailable (%s)', type(exc).__name__)
            await asyncio.sleep(5)


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run())
