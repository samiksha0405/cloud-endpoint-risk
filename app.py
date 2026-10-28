"""Flask backend: serves the dashboard and a small REST API."""
from flask import Flask, jsonify, render_template, request

import database
import risk_engine

app = Flask(__name__)
database.init_db()


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/health")
def health():
    return jsonify(status="ok")


@app.get("/api/devices")
def api_devices():
    with database.db() as conn:
        devices = [dict(r) for r in conn.execute(
            "SELECT * FROM devices ORDER BY risk_score DESC, name")]
        by_device = {d["id"]: [] for d in devices}
        for r in conn.execute("SELECT * FROM issues WHERE resolved = 0 ORDER BY points DESC"):
            by_device[r["device_id"]].append(dict(r))
        for d in devices:
            d["issues"] = by_device[d["id"]]
    return jsonify(devices)


@app.get("/api/summary")
def api_summary():
    with database.db() as conn:
        levels = {"High": 0, "Medium": 0, "Low": 0}
        for r in conn.execute("SELECT risk_level, COUNT(*) AS n FROM devices GROUP BY risk_level"):
            levels[r["risk_level"]] = r["n"]
        total = conn.execute("SELECT COUNT(*) FROM devices").fetchone()[0]
        avg = conn.execute("SELECT COALESCE(AVG(risk_score), 0) FROM devices").fetchone()[0]
        open_issues = conn.execute("SELECT COUNT(*) FROM issues WHERE resolved = 0").fetchone()[0]
    return jsonify(total=total, high=levels["High"], medium=levels["Medium"],
                   low=levels["Low"], average_score=round(avg, 1), open_issues=open_issues)


@app.get("/api/alerts")
def api_alerts():
    with database.db() as conn:
        rows = conn.execute(
            "SELECT i.id, i.device_id, d.name AS device_name, d.risk_level, i.issue_type, "
            "i.detail, i.points, i.recommended_fix FROM issues i "
            "JOIN devices d ON d.id = i.device_id WHERE i.resolved = 0 "
            "ORDER BY d.risk_score DESC, i.points DESC, d.name").fetchall()
    alerts = []
    for r in rows:
        a = dict(r)
        a["title"] = risk_engine.RULES[a["issue_type"]]["title"]
        alerts.append(a)
    return jsonify(alerts)


@app.get("/api/activity")
def api_activity():
    with database.db() as conn:
        rows = conn.execute(
            "SELECT timestamp, event, message FROM activity_log ORDER BY id DESC LIMIT 30")
        return jsonify([dict(r) for r in rows])


@app.post("/api/remediate")
def api_remediate():
    payload = request.get_json(silent=True) or {}
    issue_id = payload.get("issue_id")
    if not isinstance(issue_id, int):
        return jsonify(error="issue_id (integer) is required."), 400
    try:
        with database.db() as conn:
            result = risk_engine.remediate(conn, issue_id)
    except LookupError as err:
        return jsonify(error=str(err)), 404
    return jsonify(result)


@app.post("/api/scan")
def api_scan():
    with database.db() as conn:
        for r in conn.execute("SELECT id FROM devices").fetchall():
            risk_engine.evaluate_device(conn, r["id"])
        open_issues = conn.execute("SELECT COUNT(*) FROM issues WHERE resolved = 0").fetchone()[0]
        message = f"Scan completed: {open_issues} open issues across all devices."
        database.log_event(conn, "SCAN", message)
    return jsonify(message=message)


@app.post("/api/reset")
def api_reset():
    database.init_db(reset=True)
    return jsonify(message="Demo data reset to the original 10 devices.")


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5050, debug=True)
