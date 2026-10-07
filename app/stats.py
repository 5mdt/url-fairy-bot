# stats.py
# -*- coding: utf-8 -*-
"""`/stats` admin command text (#UFB-0049): a pure formatter over the
`metrics.snapshot()` dict. It prints only fixed platform names and numbers,
never chat IDs or URLs."""

import html


# #UFB-0049
def is_admin(chat_id: int, admin_chat_ids: list[int]) -> bool:
    """Whether `chat_id` may run `/stats`; an empty list authorizes nobody."""
    return chat_id in admin_chat_ids


# #UFB-0049
def _rate(count: int, total: int) -> str:
    return f"{count / total:.0%}" if total else "n/a"


# #UFB-0049
def _size(n: int) -> str:
    value = float(n)
    for unit in ("B", "KB", "MB"):
        if value < 1024:
            return f"{value:.0f} B" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} GB"


# #UFB-0049
def format_stats(snapshot: dict) -> str:
    """Render a `metrics.snapshot()` as HTML-safe text for the admin reply."""
    requests = snapshot.get("requests", {})
    downloads = snapshot.get("downloads", {})
    totals = {"success": 0, "failure": 0, "fallback_mirror": 0}
    for outcomes in downloads.values():
        for outcome, count in outcomes.items():
            totals[outcome] = totals.get(outcome, 0) + count
    attempts = sum(totals.values())

    lines = [
        "<b>Stats</b> (since last restart)",
        f"Requests handled: {sum(requests.values())}",
        f"Downloads: {attempts}",
        f"  success: {_rate(totals['success'], attempts)}",
        f"  failure: {_rate(totals['failure'], attempts)}",
        f"  mirror fallback: {_rate(totals['fallback_mirror'], attempts)}",
    ]
    platforms = sorted(set(requests) | set(downloads))
    if platforms:
        lines.append("Per platform:")
        for name in platforms:
            outcomes = downloads.get(name, {})
            ok = outcomes.get("success", 0)
            bad = outcomes.get("failure", 0)
            fb = outcomes.get("fallback_mirror", 0)
            lines.append(
                f"  {html.escape(name)}: {requests.get(name, 0)} requests, "
                f"{ok} ok, {bad} failed, {fb} mirror"
            )
    lines.append(f"Cache size: {_size(int(snapshot.get('cache_size_bytes', 0)))}")
    return "\n".join(lines)
