"""Rule-based risk engine: detects issues, scores devices, applies simulated fixes."""
from datetime import datetime

from database import iso, log_event, now_utc

REQUIRED_PATCH_LEVEL = 10   # devices below this patch level are "outdated"
FAILED_LOGIN_LIMIT = 5      # this many failed logins or more is suspicious
INACTIVE_DAYS = 7           # no check-in for this many days = inactive

RULES = {
    "outdated_software": {
        "title": "Outdated software",
        "points": 25,
        "fix": "Install the latest operating system updates and security patches.",
    },
    "encryption_disabled": {
        "title": "Disk encryption disabled",
        "points": 30,
        "fix": "Turn on full-disk encryption (BitLocker, FileVault or LUKS).",
    },
    "failed_logins": {
        "title": "Repeated failed logins",
        "points": 25,
        "fix": "Lock the account, reset the password and require multi-factor authentication.",
    },
    "inactive_device": {
        "title": "Inactive device",
        "points": 20,
        "fix": "Contact the owner, reconnect the device and confirm it is still in use.",
    },
}


def risk_level(score):
    if score >= 60:
        return "High"
    if score >= 30:
        return "Medium"
    return "Low"


def device_status(score, open_issue_count):
    if open_issue_count == 0:
        return "Secure"
    if score >= 60:
        return "Critical"
    return "Needs attention"


def detect_issues(device, now):
    """Apply the four simple rules. Returns {issue_type: detail}."""
    found = {}
    if device["patch_level"] < REQUIRED_PATCH_LEVEL:
        found["outdated_software"] = (
            f"Patch level {device['patch_level']} is below the required {REQUIRED_PATCH_LEVEL}."
        )
    if not device["encryption_enabled"]:
        found["encryption_disabled"] = "Disk encryption is turned off."
    if device["failed_logins"] >= FAILED_LOGIN_LIMIT:
        found["failed_logins"] = (
            f"{device['failed_logins']} failed logins (limit is {FAILED_LOGIN_LIMIT})."
        )
    days = (now - datetime.fromisoformat(device["last_seen"])).days
    if days >= INACTIVE_DAYS:
        found["inactive_device"] = f"No check-in for {days} days."
    return found


def evaluate_device(conn, device_id):
    """Re-run the rules for one device and refresh its issues, score, level and status."""
    device = dict(conn.execute("SELECT * FROM devices WHERE id = ?", (device_id,)).fetchone())
    now = now_utc()
    found = detect_issues(device, now)

    open_issues = {
        r["issue_type"]: r
        for r in conn.execute(
            "SELECT * FROM issues WHERE device_id = ? AND resolved = 0", (device_id,)
        )
    }
    for issue_type, row in open_issues.items():
        if issue_type not in found:  # no longer detected -> resolved
            conn.execute("UPDATE issues SET resolved = 1, resolved_at = ? WHERE id = ?",
                         (iso(now), row["id"]))
        else:
            conn.execute("UPDATE issues SET detail = ? WHERE id = ?",
                         (found[issue_type], row["id"]))
    for issue_type, detail in found.items():
        if issue_type not in open_issues:
            rule = RULES[issue_type]
            conn.execute(
                "INSERT INTO issues (device_id, issue_type, detail, points, recommended_fix, "
                "detected_at) VALUES (?, ?, ?, ?, ?, ?)",
                (device_id, issue_type, detail, rule["points"], rule["fix"], iso(now)),
            )

    score = min(100, sum(RULES[t]["points"] for t in found))
    level = risk_level(score)
    status = device_status(score, len(found))
    conn.execute(
        "UPDATE devices SET risk_score = ?, risk_level = ?, status = ? WHERE id = ?",
        (score, level, status, device_id),
    )
    return score, level, status


def remediate(conn, issue_id):
    """Simulate fixing one issue: change the device's state, then re-score it."""
    issue = conn.execute(
        "SELECT * FROM issues WHERE id = ? AND resolved = 0", (issue_id,)
    ).fetchone()
    if issue is None:
        raise LookupError("Issue not found or already resolved.")

    device = conn.execute("SELECT * FROM devices WHERE id = ?", (issue["device_id"],)).fetchone()
    old_score = device["risk_score"]
    kind = issue["issue_type"]

    if kind == "outdated_software":
        conn.execute("UPDATE devices SET patch_level = ? WHERE id = ?",
                     (REQUIRED_PATCH_LEVEL, device["id"]))
    elif kind == "encryption_disabled":
        conn.execute("UPDATE devices SET encryption_enabled = 1 WHERE id = ?", (device["id"],))
    elif kind == "failed_logins":
        conn.execute("UPDATE devices SET failed_logins = 0 WHERE id = ?", (device["id"],))
    elif kind == "inactive_device":
        conn.execute("UPDATE devices SET last_seen = ? WHERE id = ?",
                     (iso(now_utc()), device["id"]))

    new_score, level, status = evaluate_device(conn, device["id"])
    title = RULES[kind]["title"]
    message = (f"Remediation applied on {device['name']}: {title} fixed. "
               f"Risk score {old_score} to {new_score} ({level}), status: {status}.")
    log_event(conn, "REMEDIATION", message)
    return {"message": message, "device_id": device["id"], "old_score": old_score,
            "new_score": new_score, "risk_level": level, "status": status}
