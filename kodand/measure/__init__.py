"""
kodand.measure - Measurement spine (Tranche 0)
0.1 Re-explanation counter, 0.2 Repeated-mistake counter, 0.3 Event log, 0.4 Cost log, week report
"""
import time
import json
from datetime import datetime, timedelta
from kodand.store import get_store

def log_event(repo_path, kind, entry_id=None, provenance="", detail=""):
    get_store(repo_path).log_event(kind, entry_id, provenance, detail)

def get_week_range(week_str=None):
    """Return (start_ts, end_ts, week_label) for ISO week YYYY-Www or current week."""
    if week_str:
        y, w = week_str.split("-W")
        # ISO week start Monday
        jan4 = datetime(int(y), 1, 4)
        start = jan4 + timedelta(days=(int(w)-1)*7 - jan4.weekday())
    else:
        now = datetime.now()
        start = now - timedelta(days=now.weekday())
    start = start.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=7)
    label = f"{start.isocalendar()[0]}-W{start.isocalendar()[1]:02d}"
    return start.timestamp(), end.timestamp(), label

def north_star_report(repo_path=None, week_str=None):
    import os
    repo_path = repo_path or os.getcwd()
    store = get_store(repo_path)
    start_ts, end_ts, label = get_week_range(week_str)
    start_iso = datetime.fromtimestamp(start_ts).isoformat()
    end_iso = datetime.fromtimestamp(end_ts).isoformat()
    # Count events in week
    conn = store._get_conn()
    def count_kind(k):
        return conn.execute("SELECT COUNT(*) FROM events WHERE kind=? AND ts>=? AND ts<?", (k, start_iso, end_iso)).fetchone()[0]
    captured = count_kind("captured")
    blocked = count_kind("blocked")
    held = count_kind("held")
    validated = count_kind("validated")
    retired = count_kind("retired")
    reexpl = count_kind("reexplanation")
    repeated = count_kind("repeated_mistake")
    # outcome = explicit outcome labels (avoided/caused/noise) plus legacy 'outcome' kind
    outcome = count_kind("outcome") + count_kind("outcome_label")
    # outcome includes blocked/held etc? Use separate
    conn.close()
    # repeated-mistake rate = repeated_mistakes / outcome_events if outcome>0 else n/a
    if outcome>0:
        rate = round(repeated/outcome,3)
        rate_s = str(rate)
    else:
        rate = None
        rate_s = "n/a (no outcome events in week)"
    return {
        "week_start": datetime.fromtimestamp(start_ts).date().isoformat(),
        "week_end": datetime.fromtimestamp(end_ts).date().isoformat(),
        "label": label,
        "repeated_mistakes": repeated,
        "outcomes": outcome,
        "rate": rate,
        "rate_s": rate_s,
        "re_explanations": reexpl,
        "captured": captured,
        "blocked": blocked,
        "held": held,
        "validated": validated,
        "retired": retired,
    }

def format_report(r):
    lines = [
        f"week {r['label']} ({r['week_start']} .. {r['week_end']})",
        f"repeated-mistake count : {r['repeated_mistakes']}",
        f"outcome events         : {r['outcomes']}",
        f"repeated-mistake rate  : {r['rate_s']}",
        f"re-explanation count   : {r['re_explanations']}",
        f"captured               : {r['captured']}",
        f"blocked                : {r['blocked']}",
        f"held                   : {r['held']}",
        f"validated              : {r['validated']}",
        f"retired                : {r.get('retired',0)}",
    ]
    return "\n".join(lines)
