# Demo data

This folder contains a small fake demo dataset for the compliance MVP tutorial.
It is intended for local development and portfolio demos only.

## Contents

```text
examples/demo/
├── seed_demo_data.sql
├── attachments/
│   ├── demo-data-encryption-audit.pdf
│   ├── demo-server-room-access-photo.jpg
│   ├── demo-retention-policy-review.pdf
│   ├── demo-ai-bias-audit-summary.pdf
│   ├── demo-remediation-plan.pdf
│   └── demo-transfer-register-gap.pdf
├── results/
│   ├── load_history.png
│   ├── load_attachments1.png
│   └── load_attachments2.png
└── README.md
```

The data centers on demo `site_id = 71`, which has multiple certifications,
findings, and linked attachment records. The attachment files are fake and
contain no real client information.

## Prerequisites

### Copy the database attachments

For both Docker and local runs, you should then copy the fake attachment files into 
the backend runtime storage directory:

```bash
mkdir -p backend/storage/attachments
cp examples/demo/attachments/* backend/storage/attachments/
```

## Mounting the servers

There are two routes listed here: using Docker or launching locally. In both
cases, the demo can run in mock AI mode or Anthropic AI mode. Mock mode does
not require internet access or an API key. Anthropic mode requires internet
access and a valid Anthropic API key. See the repo README.md for instructions
on setting up an Anthropic API key.

### Docker instructions

When using Docker Compose, the backend should connect to the `postgres` service
and the database should already exist before this seed file is loaded.

Create the Docker environment file from the template:

```bash
cp docker/.env.example docker/.env
```

For offline demos, keep the default mock AI mode in `docker/.env`:

```env
AI_MODE=mock
ANTHROPIC_API_KEY=
```

For live Anthropic analysis, edit `docker/.env`:

```env
AI_MODE=anthropic
ANTHROPIC_API_KEY=your_anthropic_api_key_here
```

Then launch the Docker containers from the project root with the Docker
environment file:

```bash
docker compose --env-file docker/.env up -d --build
```

From the repository root, with Docker Compose running:

```bash
docker compose --env-file docker/.env exec -T postgres psql -U postgres -d compliance_db < examples/demo/seed_demo_data.sql
```

### Local run instructions

Create the local backend environment file from the template:

```bash
cp backend/.env.example backend/.env
```

Use the same `AI_MODE` values described above in `backend/.env`.

Run migrations before loading the demo data from the project root:

```bash
alembic upgrade head
```

If launching without Docker, the backend can be launched from the root folder with:

```bash
fastapi dev backend/src/compliance/api/main.py 
```

and the frontend can be launched in another terminal from the frontend folder with:
```bash
npm run build
npm run dev
```

If you are running PostgreSQL directly on your host instead of Docker:

```bash
psql -h localhost -U postgres -d compliance_db -f examples/demo/seed_demo_data.sql
```

## Running the demo

Open the frontend (normally at http://localhost:5173/ in your browser) and use:

```text
Site ID: 71
```

Suggested demo flow:

```text
Load History
Load Attachments
Run AI Analysis
Generate Markdown
Download Markdown
```

Sample screenshots for "Load History" and "Load Attachments" can be found in
the examples/demo/results/ folder.

After loading the demo site, click **Run AI Analysis** to generate a structured
analysis for `site_id = 71`. In mock mode, this response is deterministic and
can be generated without internet access. In Anthropic mode, the backend sends
the site history to Anthropic and returns a live AI-generated analysis.

After the analysis appears, click **Generate Markdown** to preview the report,
then click **Download Markdown** to save it locally. The downloaded markdown can
be compared with the saved demo result file:

```text
examples/demo/results/site-71-analysis.md
```

## Notes

- The seed script is designed for local demo use and truncates the demo tables
  before inserting records.
- Do not use this seed file against a database containing real data.
- Attachment files in this folder are canonical demo inputs. The backend runtime
  storage directory is `backend/storage/attachments/`.
- The AI analysis shown in the frontend is a draft preview and requires human
  review. It is not an official compliance decision.
