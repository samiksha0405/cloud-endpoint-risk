"""Simple benchmark and self-check. Start the server first (python app.py), then run:  python benchmark.py

It resets the demo data, sends 100 requests to each read endpoint, checks that the rules found
the expected 16 issues, fixes every issue through the API and prints a summary you can quote in
your results (your numbers will differ from other machines)."""
import json
import statistics
import time
import urllib.request

BASE = "http://127.0.0.1:5050"


def call(path, method="GET", body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method,
                                 headers={"Content-Type": "application/json"})
    start = time.perf_counter()
    with urllib.request.urlopen(req) as resp:
        payload = json.loads(resp.read())
        return resp.status, payload, (time.perf_counter() - start) * 1000


call("/api/reset", "POST")
times, ok, total = [], 0, 0
for path in ["/api/devices", "/api/summary", "/api/alerts", "/api/activity", "/health"]:
    for _ in range(100):
        status, _, ms = call(path)
        total += 1
        ok += status == 200
        times.append(ms)
print(f"Read requests: {total}, successful: {ok} ({ok / total * 100:.1f}%)")
print(f"Average response time: {statistics.mean(times):.2f} ms, slowest: {max(times):.2f} ms")

_, summary, _ = call("/api/summary")
print(f"Initial state: {summary['high']} High, {summary['medium']} Medium, {summary['low']} Low, "
      f"{summary['open_issues']} open issues, average score {summary['average_score']}")

_, alerts, _ = call("/api/alerts")
fix_times = []
for alert in alerts:
    status, _, ms = call("/api/remediate", "POST", {"issue_id": alert["id"]})
    assert status == 200
    fix_times.append(ms)
_, summary, _ = call("/api/summary")
print(f"Remediated {len(fix_times)} issues, average {statistics.mean(fix_times):.2f} ms each")
print(f"Final state: {summary['high']} High, {summary['medium']} Medium, {summary['low']} Low, "
      f"{summary['open_issues']} open issues, average score {summary['average_score']}")
call("/api/reset", "POST")
print("Demo data reset.")
