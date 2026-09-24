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


---

# Installation & Setup

## Prerequisites

Install the following tools:

- Git
- Python 3.12
- Docker
- kubectl
- Helm 3
- Minikube
- ArgoCD (for the GitOps section)

Verify the installation:

```bash
git --version
python3 --version
docker --version
kubectl version --client
helm version
minikube version
```

## Clone the Repository

```bash
git clone <YOUR_REPOSITORY_URL>
cd notes-app-deployment
```

Replace `<YOUR_REPOSITORY_URL>` with the repository URL.

---

## Run the Application Locally

This is a basic sanity check before containerization.

### Start PostgreSQL

```bash
docker run -d --name notes-postgres \
  -e POSTGRES_USER=notes \
  -e POSTGRES_PASSWORD=notes \
  -e POSTGRES_DB=notes \
  -p 5432:5432 \
  postgres:16
```

### Create the Python Environment

```bash
cd app
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Configure the application using `.env.example`, then start the API:

```bash
uvicorn main:app --reload
```

Test the API:

```bash
curl localhost:8000/healthz
curl localhost:8000/readyz
curl -X POST localhost:8000/notes \
  -H 'content-type: application/json' \
  -d '{"title":"hello","content":"world"}'
curl localhost:8000/notes
```

---

## Build and Run with Docker

From the repository root:

```bash
docker build -t notes-api:local -f app/Dockerfile app
```

Run the API container:

```bash
docker run --rm -p 8000:8000 \
  -e POSTGRES_HOST=host.docker.internal \
  -e POSTGRES_PORT=5432 \
  -e POSTGRES_DB=notes \
  -e POSTGRES_USER=notes \
  -e POSTGRES_PASSWORD=notes \
  notes-api:local
```

Verify:

```bash
curl localhost:8000/healthz
curl localhost:8000/readyz
```

Check the image:

```bash
docker images notes-api
```

---

## Deploy with Helm on Minikube

Start Minikube:

```bash
minikube start
```

Verify the cluster:

```bash
kubectl get nodes
```

Make the local Docker image available to Minikube:

```bash
minikube image load notes-api:local
```

Build the PostgreSQL dependency:

```bash
helm dependency build helm/notes-api
```

Validate the chart:

```bash
helm lint helm/notes-api

helm template notes-dev helm/notes-api \
  -f helm/notes-api/values-dev.yaml
```

Install the development environment:

```bash
helm install notes-dev helm/notes-api \
  -f helm/notes-api/values-dev.yaml \
  --namespace notes-dev \
  --create-namespace
```

Check the resources:

```bash
kubectl get pods -n notes-dev
kubectl get svc -n notes-dev
kubectl get pvc -n notes-dev
```

Access the API:

```bash
kubectl port-forward \
  -n notes-dev \
  svc/notes-dev-notes-api 8000:8000
```

Then test:

```bash
curl http://localhost:8000/healthz
curl http://localhost:8000/readyz

curl -X POST http://localhost:8000/notes \
  -H 'content-type: application/json' \
  -d '{"title":"hello","content":"world"}'

curl http://localhost:8000/notes
```

---

## Production Helm Configuration

Production uses `values-prod.yaml`.

The production configuration differs from development through:

- 2 API replicas
- Higher CPU and memory resources
- PostgreSQL persistence enabled
- Persistent storage configured for PostgreSQL

Validate the production configuration:

```bash
helm lint helm/notes-api

helm template notes-prod helm/notes-api \
  -f helm/notes-api/values-prod.yaml
```

---

## GitHub Actions CI

The CI pipeline is located at:

```text
.github/workflows/ci.yaml
```

It runs on pull requests and performs:

- Ruff linting
- Docker image build using the Git commit SHA
- Trivy image vulnerability scanning
- Helm dependency build
- Helm lint
- Helm template rendering
- Trivy Kubernetes configuration scanning

The Trivy image and configuration scans use HIGH/CRITICAL severity gates.

No local CI setup is required because GitHub Actions runs the workflow on the GitHub runner.

---

## Deploy with ArgoCD

ArgoCD is used for the GitOps deployment.

The Application manifests are:

```text
argocd/
├── notes-api-dev.yaml
└── notes-api-prod.yaml
```

### Install ArgoCD

```bash
kubectl create namespace argocd
```

```bash
kubectl apply -n argocd \
  --server-side \
  --force-conflicts \
  -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
```

Verify:

```bash
kubectl get pods -n argocd
```

### Deploy Development

```bash
kubectl apply -f argocd/notes-api-dev.yaml
```

Check:

```bash
kubectl get applications -n argocd
kubectl get pods -n notes-dev
kubectl get svc -n notes-dev
```

### Deploy Production

```bash
kubectl apply -f argocd/notes-api-prod.yaml
```

Production is configured for manual synchronization after reviewing the desired state.

---

## Useful Verification Commands

Check resources across namespaces:

```bash
kubectl get pods -A
```

Check Helm releases:

```bash
helm list -A
```

Check ArgoCD Applications:

```bash
kubectl get applications -n argocd
```

Inspect ArgoCD Applications:

```bash
kubectl describe application notes-api-dev -n argocd
kubectl describe application notes-api-prod -n argocd
```

Inspect Kubernetes events:

```bash
kubectl get events -A --sort-by=.lastTimestamp
```
