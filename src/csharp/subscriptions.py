"""Observe repeated event subscriptions across code-behind and Designer partials."""
from collections import Counter
import re

from src.common.results import Issue
from .lexer import _scan_csharp

# `x.Event += handler;`, `x.Event += new Delegate(this.handler);`, `Event += handler;`.
# Lambdas and anonymous methods are excluded: each one is a distinct delegate.
_SUBSCRIPTION = re.compile(
    r'(?<![\w.])(?P<target>(?:this\s*\.\s*)?(?:[A-Za-z_]\w*\s*\.\s*)*[A-Za-z_]\w*)\s*'
    r'(?P<op>\+=|-=)\s*(?:new\s+[\w.<>]+\s*\(\s*)?(?:this\s*\.\s*)?(?P<handler>[A-Za-z_]\w*)\s*\)?\s*;')


def subscription_counts(source: str) -> Counter:
    """Sequential `+=`/`-=` count (floored at zero) per (receiver, event, handler), ignoring comments and literals."""
    masked = _scan_csharp(source)[0]
    counts: Counter = Counter()
    for match in _SUBSCRIPTION.finditer(masked):
        parts = [part.strip() for part in match['target'].split('.')]
        if parts and parts[0] == 'this':
            parts = parts[1:]
        if not parts:
            continue
        receiver, event = ('.'.join(parts[:-1]) or 'this'), parts[-1]
        key = (receiver, event, match['handler'])
        # Removing a delegate that is not subscribed is a no-op, so never go below zero.
        counts[key] = counts[key] + 1 if match['op'] == '+=' else max(0, counts[key] - 1)
    return +counts


def check_duplicate_subscriptions(sources: list[str], originals: list[str] | None = None) -> list[Issue]:
    """Report a handler subscribed more than once to the same event, when newly so.

    Every partial of one class is combined, so a Designer subscription repeated in
    the constructor is found. A duplicate already present in the originals is
    not reported again. Subscriptions inside repeatedly called methods and
    runtime unsubscription paths remain unverified.
    """
    current = Counter()
    for source in sources:
        current.update(subscription_counts(source))
    before = Counter()
    for source in originals or []:
        before.update(subscription_counts(source))
    issues = []
    for (receiver, event, handler), count in sorted(current.items()):
        if count > 1 and count > before.get((receiver, event, handler), 0):
            issues.append(Issue('duplicate_event_subscription', 'warning',
                'The same handler is subscribed more than once to this event, so it runs repeatedly per event '
                '(for example a double save). Keep one subscription unless the repetition is the verified requirement.',
                details={'receiver': receiver, 'event': event, 'handler': handler, 'subscriptions': count}))
    return issues
