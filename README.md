# Notes API — DevOps Intern Assignment

A minimal FastAPI + PostgreSQL backend. This repo is your starting point — the
Python app is done and working; your job is everything around it
(containerization, Helm, CI/CD, GitOps). Full instructions: **[ASSIGNMENT.md](ASSIGNMENT.md)**.

## Running the app locally (no Docker) — sanity check only

You'll need a local Postgres, or point it at any reachable one:

```bash
cd app
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env   # edit if your local Postgres differs
export $(cat .env | xargs)

uvicorn main:app --reload
```

Then:
```bash
curl localhost:8000/healthz
curl localhost:8000/readyz
curl -X POST localhost:8000/notes -H 'content-type: application/json' \
  -d '{"title":"hello","content":"world"}'
curl localhost:8000/notes
```

This step is optional — it's just to help you understand the app before you
containerize it. The real deliverables start in `ASSIGNMENT.md`.
