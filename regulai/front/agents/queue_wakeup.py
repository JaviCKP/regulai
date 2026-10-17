"""PostgreSQL wakeups are hints; durable claim/authorization remains authoritative."""
from contextlib import contextmanager
import threading

from django.db import DatabaseError, connection

CHANNEL = 'regulay_agent_jobs'
# A synchronous claim may wait only with an isolated request thread/connection.
# Bound those resources even if extra executors use the same worker credential.
_WAITERS = threading.BoundedSemaphore(4)


def notify():
    """Empty payload: never expose an account, execution, prompt or credential.

    PostgreSQL delivers NOTIFY only when the surrounding transaction commits;
    a rollback therefore cannot announce an uncommitted execution.
    """
    if connection.vendor == 'postgresql':
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_notify(%s, '')", [CHANNEL])


@contextmanager
def listen():
    """Subscribe before checking durable state, closing the check/wait race.

    Reuse this request's connection without holding any transaction or lock
    while waiting. A connection failure, unsupported driver or waiter limit
    falls back to the ordinary bounded worker poll.
    """
    acquired = False
    raw = None
    listening = False
    try:
        if (connection.vendor == 'postgresql' and not connection.in_atomic_block
                and connection.get_autocommit()):
            acquired = _WAITERS.acquire(blocking=False)
            if acquired:
                connection.ensure_connection()
                raw = connection.connection
                if callable(getattr(raw, 'notifies', None)):
                    with connection.cursor() as cursor:
                        cursor.execute('LISTEN ' + CHANNEL)
                    listening = True
    except (DatabaseError, connection.Database.Error):
        # Claim still performs the normal database/authorization checks.
        listening = False

    def wait(seconds):
        if not listening:
            return False
        notifications = raw.notifies(timeout=max(0, seconds), stop_after=1)
        try:
            return next(notifications, None) is not None
        finally:
            notifications.close()

    try:
        yield wait if listening else None
    finally:
        try:
            if listening and not raw.closed:
                with connection.cursor() as cursor:
                    cursor.execute('UNLISTEN ' + CHANNEL)
        except (DatabaseError, connection.Database.Error):
            # Do not return a subscribed/broken session to Django's reuse path.
            connection.close()
        finally:
            if acquired:
                _WAITERS.release()
