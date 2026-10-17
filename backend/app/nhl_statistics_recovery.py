"""One explicit operator recovery using public, allowlisted downloads.

From backend/: ENABLE_NHL_ADVANCED_STATS=true python -m
app.nhl_statistics_recovery --run

Uses this project's existing private database configuration. No dashboard
cookie, proxy, alternate source, paid API call or scheduler is involved.
"""
import argparse
import asyncio
import json

from . import db, nhl_advanced
from .config import settings
from .limits import BudgetExceeded


async def recover(*, transport=None):
    if not settings.nhl_advanced_enabled:
        raise BudgetExceeded('Enable NHL advanced statistics before manual recovery')
    admission = await nhl_advanced.reserve_manual_recovery()
    return await nhl_advanced.sync(transport=transport, admission=admission,
                                  acquisition='operator_public_download')


async def main():
    try:
        db.configure_database()
        result = await recover()
        print(json.dumps(result))
        return 0 if result.get('status') == 'succeeded' else 1
    except BudgetExceeded as exc:
        print(json.dumps({'status': 'blocked', 'reason': str(exc), 'paid_credits': 0}))
        return 1
    except Exception as exc:
        # Do not print connection URLs, credentials or upstream response bodies.
        print(json.dumps({'status': 'failed', 'category': type(exc).__name__, 'paid_credits': 0}))
        return 1
    finally:
        if db.engine is not None:
            await db.engine.dispose()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Guarded manual recovery of public NHL statistics')
    parser.add_argument('--run', action='store_true', required=True,
                        help='Explicitly admit one bounded recovery; failed attempts remain consumed')
    parser.parse_args()
    raise SystemExit(asyncio.run(main()))
