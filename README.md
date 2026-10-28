# Cloud-Based Endpoint Risk Detection and Remediation System

A beginner-level cloud computing prototype. A Flask API and SQLite database monitor **10 simulated devices**,
detect security risks with simple rules, show alerts with recommended fixes, and let you **simulate remediation**
from a web dashboard. Everything runs locally and for free. No real devices, paid APIs or external services are used.

## Setup and run

Requires Python 3.9 or newer.

**Windows (PowerShell)**
```powershell
cd cloud-endpoint-risk
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

**macOS / Linux**
```bash
cd cloud-endpoint-risk
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python3 app.py
```

Open **http://127.0.0.1:5050** in your browser. Stop the server with `Ctrl+C`.

The database file `endpoint_risk.db` is created and filled with the 10 sample devices on first start.
Use **Reset demo data** on the dashboard (or delete `endpoint_risk.db`) to start over.

If port 5050 is busy, change `port=5050` in the last line of `app.py`.

## Project structure

```
cloud-endpoint-risk/
├── app.py              Flask server and REST API routes
├── risk_engine.py      Detection rules, risk scoring, simulated remediation
├── database.py         SQLite schema, connection helper, sample data
├── requirements.txt    Flask only
├── templates/
│   └── index.html      Dashboard page
├── static/
│   ├── style.css       Dashboard styling
│   ├── app.js          Calls the API and redraws the page
│   └── architecture.svg  Architecture diagram (used in the report and slides)
└── endpoint_risk.db    Created automatically on first run
```

## Detection rules and scoring

Each rule that matches adds points. The score is capped at 100.

| Rule | Triggers when | Points | Recommended fix |
|---|---|---|---|
| Outdated software | patch level below 10 | 25 | Install latest OS updates and security patches |
| Disk encryption disabled | encryption is off | 30 | Turn on BitLocker, FileVault or LUKS |
| Repeated failed logins | 5 or more failed logins | 25 | Lock account, reset password, require MFA |
| Inactive device | no check-in for 7 or more days | 20 | Contact owner and reconnect the device |

| Score | Risk level | Status |
|---|---|---|
| 0 | Low | Secure |
| 1 to 29 | Low | Needs attention |
| 30 to 59 | Medium | Needs attention |
| 60 to 100 | High | Critical |

The thresholds are constants at the top of `risk_engine.py`.

## Using the dashboard

1. Read the **risk summary** tiles and the colored distribution bar. Click a tile (High risk, Medium risk, Low risk, Devices, Average score, Open issues) to filter the device table and alerts; click it again or press **Show all devices** to clear the filter.
2. Review the **device table**. It is sorted from highest to lowest risk.
3. Click a device (or an alert) to open it in the **Remediation** panel.
4. Select one issue, then click **Simulate Remediation**.
5. Watch the device's score, level and status update, and see the new entry in the **Activity log**.
6. **Run scan** re-evaluates every device. **Reset demo data** restores the original 10 devices.

Sample fleet: 2 High, 4 Medium and 4 Low devices. `LAPTOP-SUP-09` starts at 100 with all four issues, which makes a
good demo: fix its issues one by one and watch it fall from High to Low and then Secure.

## REST API

| Method | Route | Purpose |
|---|---|---|
| GET | `/api/devices` | All devices with their open issues |
| GET | `/api/summary` | Counts per risk level, average score, open issues |
| GET | `/api/alerts` | Open issues with recommended fixes |
| GET | `/api/activity` | Latest activity log entries |
| POST | `/api/remediate` | Body `{"issue_id": 3}`: fix one issue and re-score the device |
| POST | `/api/scan` | Re-run all rules on all devices |
| POST | `/api/reset` | Reload the sample data |
| GET | `/health` | Health check (used by cloud load balancers) |

## Cloud computing concepts demonstrated

- **Client-server and three-tier architecture.** Browser (presentation), Flask (application), SQLite (data).
- **REST API over HTTP and JSON.** The dashboard only talks to the server through the API, so any other client could too.
- **Centralized monitoring (SaaS style).** One dashboard shows the state of many endpoints, which is how cloud security tools such as Microsoft Defender for Endpoint or CrowdStrike present data.
- **Persistent cloud-style data store.** Devices, issues and the audit trail live in a database, not in the browser.
- **Automated remediation.** A detected risk maps to a recommended action that is applied through an API call.
- **Health endpoint.** `/health` is the kind of check load balancers use to decide whether an instance is alive.

```
 Presentation tier          Application tier               Data tier
┌──────────────────┐ HTTP ┌─────────────────────────┐ SQL ┌──────────────────┐
│ Web dashboard    │─────>│ Flask server            │<───>│ SQLite database  │
│ HTML, CSS, JS    │<─────│ REST API + risk engine  │     │ devices, issues, │
└──────────────────┘ JSON └────────────▲────────────┘     │ activity_log     │
                                       │                  └──────────────────┘
                          10 simulated devices (sample data)
```

## How this could be deployed to the cloud

The code is already split into tiers, so each tier maps to a managed cloud service:

| Prototype piece | Cloud equivalent (AWS / Azure / Google Cloud) |
|---|---|
| `templates/` and `static/` | Static hosting with a CDN (S3 + CloudFront / Blob Storage + Front Door / Cloud Storage + CDN) |
| Flask app (`app.py`) | A container or VM behind a load balancer (Elastic Beanstalk or App Runner / App Service / Cloud Run), run with Gunicorn |
| SQLite file | A managed database such as PostgreSQL (RDS / Azure Database / Cloud SQL), because a file cannot be shared by several servers |
| Sample data and `/api/scan` | Real agents on devices sending telemetry to the API, with scans run by a scheduled function (Lambda / Functions / Cloud Scheduler) |
| Activity log table | Central logging and alerting (CloudWatch / Azure Monitor / Cloud Logging) |
| Open local access | HTTPS, user login and role-based access (IAM, Cognito or Entra ID), secrets kept in a secrets manager |

Moving to the cloud would let the app scale across several instances, survive a server failure, be reached from
anywhere, and keep its data backed up. Packaging the app in a Docker container is the usual first step because the same
image then runs on any of the services above.

## Deploy it to a real cloud (free)

The project is cloud-ready: it has a production server (Gunicorn), a `Dockerfile` and a `render.yaml`.

**Option A: Render free web service (no credit card needed)**
1. Create a GitHub repository and push this folder to it (`git init`, `git add .`, `git commit -m "first"`, then push).
2. On render.com choose **New > Blueprint**, pick the repository, and approve. Render reads `render.yaml`.
   (Or **New > Web Service** with build command `pip install -r requirements.txt` and start command
   `gunicorn app:app --bind 0.0.0.0:$PORT --workers 1 --threads 4`; set the health check path to `/health`.)
3. When the deploy finishes, open the public `https://....onrender.com` URL. Take a screenshot for your report.

Free-tier behaviour to expect: the service sleeps after 15 minutes without traffic and takes up to a minute to wake;
its filesystem is temporary, so the SQLite file is recreated (with the 10 sample devices) after every restart.

**Option B: any container host (AWS App Runner, Azure Container Apps, Google Cloud Run, a VM with Docker)**
```bash
docker build -t endpoint-risk .
docker run -p 8080:8080 endpoint-risk      # open http://127.0.0.1:8080
```

Run it locally the production way to check it first:
```bash
gunicorn app:app --bind 127.0.0.1:8080 --workers 1 --threads 4
```
Use one worker because SQLite is a single file; a managed PostgreSQL database is what lets you scale to many workers.

## Limits of this prototype

It is a teaching demo: devices are simulated, rules are deliberately simple, there is no login, and the Flask
development server is used. Do not expose it to the internet as is.
