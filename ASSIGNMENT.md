# DevOps Intern Take-Home Assignment

## Context

Our production stack: containerized services on **AWS EKS**, images built via
**GitHub Actions** with security scanning (**Trivy**) baked into the pipeline,
and deployments managed with **GitOps** — **ArgoCD** watching **Helm** charts
in git as the source of truth. This assignment mirrors that stack end to end,
scaled down to something you can run on your laptop.

You're given a small, working **FastAPI + PostgreSQL** backend (a "Notes API")
in `app/`. You don't need to change the application code. Your job is
everything around it: containerize it, package it for Kubernetes, wire up a
CI pipeline, and describe how it would be deployed via GitOps.

**Time budget:** this is scoped for a part-time take-home over about a week —
plan for roughly 6-10 hours total, spread out however works for you. Part 5 is
explicitly a stretch section; a strong submission can skip it or leave parts
of it as a written proposal rather than working code.

You're free to use docs, blog posts, and AI tools — just make sure you
understand and can explain everything you submit; we'll ask you to walk
through your decisions.

## What you need locally

- Docker
- A local Kubernetes cluster: [kind](https://kind.sigs.k8s.io/) or minikube
  (either is fine — we don't expect real AWS/EKS access for this exercise;
  everything here should work identically on kind)
- `helm` v3
- `kubectl`
- (Part 4) ArgoCD running in your local cluster — a one-command install, see
  Part 4

---

## Part 1 — Containerize the app

Write a `Dockerfile` for the app in `app/`.

Requirements:
- Multi-stage build (a builder stage for dependencies, a slim runtime stage)
- Runs as a **non-root** user
- Uses a pinned, slim base image (e.g. `python:3.12-slim`), not `latest`
- Sensible `.dockerignore`
- A `HEALTHCHECK` instruction, or explain in your write-up why you'd rely on
  Kubernetes probes instead
- Final image should be reasonably small — check with `docker images`

Verify it works:
```bash
docker build -t notes-api:local -f app/Dockerfile app
docker run --rm -p 8000:8000 \
  -e POSTGRES_HOST=host.docker.internal \
  -e POSTGRES_PASSWORD=notes \
  notes-api:local
```
(You'll need a reachable Postgres for this to actually serve traffic — a
`docker run -e POSTGRES_PASSWORD=notes -p 5432:5432 postgres:16` in another
terminal works, or just confirm `/healthz` responds and note that `/readyz`
correctly reports 503 without a DB.)

**Where this goes:** `app/Dockerfile`, `app/.dockerignore`

---

## Part 2 — Helm chart with a database dependency

This is the core of the assignment. Write a Helm chart for the Notes API
that:

1. **Deploys the app** with a `Deployment`, `Service`, `ConfigMap` (non-secret
   config: `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB`), and a
   `ServiceAccount`.
2. **Declares PostgreSQL as a chart dependency** — add an existing community
   chart (e.g. `oci://registry-1.docker.io/bitnamicharts/postgresql`, or the
   Bitnami Helm repo equivalent) in `Chart.yaml` under `dependencies:`, run
   `helm dependency build`, and configure it via your parent chart's
   `values.yaml` (`postgresql.auth.database`, `postgresql.auth.username`,
   etc.). This is the realistic pattern: you're not writing your own Postgres
   templates, you're consuming and configuring someone else's chart as a
   subchart.
3. **Wires the subchart's generated Secret into your app.** The
   `bitnami/postgresql` chart creates a Secret holding the password. Your
   app's `Deployment` should read `POSTGRES_PASSWORD` from that Secret via
   `secretKeyRef` — don't put the password in your own values.yaml in plain
   text. This is the single most important thing we're checking in this
   section: do you understand how to reference a dependency's generated
   Secret instead of duplicating the value?
4. **Liveness/readiness probes** wired to `/healthz` and `/readyz`.
5. **Resource requests/limits** on the app container.
6. **`values.yaml`** with sane defaults, plus **`values-dev.yaml`** and
   **`values-prod.yaml`** override files that differ meaningfully (e.g.
   replica count, resource sizing, `postgresql.persistence.enabled`,
   image tag/pullPolicy). Don't just duplicate values.yaml — pick 3-4 fields
   that would plausibly differ between environments and override only those.
7. A `NOTES.txt` printed on install/upgrade with how to reach the service
   (e.g. `kubectl port-forward` instructions).

Bonus (optional, don't block on these):
- `HorizontalPodAutoscaler` template, gated by a `.Values.autoscaling.enabled`
  flag
- `Ingress` template, same pattern
- A helper template (`_helpers.tpl`) for consistent labels/names instead of
  repeating `{{ .Release.Name }}-notes-api` everywhere

Verify it works end to end on your local cluster:
```bash
helm dependency build helm/notes-api
helm install notes-dev helm/notes-api -f helm/notes-api/values-dev.yaml
kubectl get pods,svc
kubectl port-forward svc/notes-dev-notes-api 8000:8000
curl localhost:8000/readyz   # should be 200 once postgres subchart is up
curl -X POST localhost:8000/notes -d '{"title":"it works"}' -H 'content-type: application/json'
helm upgrade notes-prod helm/notes-api -f helm/notes-api/values-prod.yaml --install
```

Also run `helm lint helm/notes-api` and `helm template helm/notes-api` and
make sure both are clean — include that in your write-up.

**Where this goes:** `helm/notes-api/`

---

## Part 3 — CI pipeline (GitHub Actions)

Add a workflow at `.github/workflows/ci.yaml` that runs on pull requests and
covers:

1. **Python checks** — install deps, run at minimum a lint step (`ruff` or
   `flake8`) and, if you add any, tests (`pytest`).
2. **Build the Docker image** from Part 1. Tag it with the git SHA. You don't
   need real push access to a registry — building it in CI (`docker build`)
   is enough; pushing to GHCR/Dockerhub is a nice-to-have if you want to wire up
   `GITHUB_TOKEN`/`DOCKERHUB_TOKEN` permissions, but not required.
3. **Trivy scan** — run `aquasecurity/trivy-action` against the built image
   (`image` scan type). Fail the build on `HIGH`/`CRITICAL` findings, or
   explain in your write-up why you chose a different severity gate.
4. **Trivy config scan** (or `helm lint` + `trivy config`) against your Helm
   chart / rendered manifests, catching misconfigurations (e.g. containers
   running as root, missing resource limits) — this is the "devsecops
   shifts left into IaC" part, not just image scanning.
5. Jobs should be reasonably fast and fail clearly — if something fails,
   the log should make it obvious why without digging.

**Where this goes:** `.github/workflows/ci.yaml`

---

## Part 4 — GitOps with ArgoCD

You don't need to run this against a real cluster with a real git remote if
that's impractical — a correct, well-explained manifest plus a description of
the sync flow is an acceptable substitute for a live demo. If you do want to
run it live:

```bash
kubectl create namespace argocd
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
```

Write an ArgoCD `Application` manifest (`argocd/notes-api-dev.yaml`, and
ideally a `notes-api-prod.yaml` too) that:
- Points at your chart path in this repo (`helm/notes-api`) and the
  appropriate `values-dev.yaml` / `values-prod.yaml` as `helm.valueFiles`
- Sets a sync policy — decide whether `automated: {prune: true, selfHeal:
  true}` is appropriate for prod vs dev, and explain your choice
- Targets the correct destination namespace per environment

In your write-up, briefly answer: if someone edits `values-prod.yaml` and
merges it to `main`, what's the sequence of events from that merge to the
new pod running? Where would you look if it *didn't* roll out?

**Where this goes:** `argocd/`

---

## Part 5 — Stretch (optional, pick what interests you)

Do as much or as little of this as your time budget allows. Partial or
written-only answers are fine here — we're more interested in your reasoning
than a fully working implementation.

- **Secrets management proposal:** the Helm chart above still has secrets
  flowing through `helm install -f values-prod.yaml` and plain Kubernetes
  Secrets (base64, not encrypted at rest by default). Write a short
  (~half page) proposal for how you'd handle this properly in a GitOps world
  where `values-prod.yaml` is committed to git — pick one of **Sealed
  Secrets**, **External Secrets Operator** (backed by AWS Secrets Manager,
  given we're on EKS), or **SOPS**, and explain why, plus what changes in the
  chart and in the ArgoCD Application to support it.
- **Monitoring hooks:** add a `/metrics` endpoint (e.g.
  `prometheus-fastapi-instrumentator`) or, if you'd rather not touch app
  code, add the standard `prometheus.io/scrape` annotations to the
  `Service`/pod template and describe what a Prometheus `ServiceMonitor`
  for this app would look like and what 2-3 alerts you'd define (e.g. error
  rate, readiness flapping).
- **Autoscaling under load:** if you didn't already add the HPA in Part 2,
  add one now, and describe (or actually run) a quick load test showing it
  scale.
- **Image supply chain:** sign the image (`cosign`) in CI, or add SBOM
  generation (`trivy image --format cyclonedx`) as a pipeline artifact.

---

## Deliverables

A single repo (fork of this one, or a zip if you don't want to use GitHub)
containing:
- Everything from Parts 1-4
- A **`WRITEUP.md`** covering, per part: what you built, the commands you ran
  to verify it, any trade-offs or things you'd do differently with more time,
  and answers to the specific questions asked above (Part 2 point 3, Part 4).
  This matters as much as the code — we want to see how you think, not just
  the final artifact.

## Evaluation rubric

| Area | Weight | What we're looking for |
|---|---|---|
| Dockerfile | 15% | Multi-stage, non-root, small image, pinned base |
| Helm chart — app templates | 20% | Correct Deployment/Service/ConfigMap, probes, resource limits, templating hygiene (no hardcoded names) |
| Helm chart — DB dependency | 20% | Correctly declared as a subchart dependency, configured via values, **password sourced from the subchart's Secret rather than duplicated** |
| Environment overrides | 10% | `values-dev.yaml`/`values-prod.yaml` differ meaningfully and sensibly |
| CI pipeline | 15% | Lint/test, image build, Trivy image scan with a real severity gate, IaC/config scan |
| GitOps / ArgoCD | 10% | Correct Application manifest, sensible sync policy reasoning, clear explanation of the rollout path |
| Write-up & reasoning | 10% | Clear explanation of decisions and trade-offs; awareness of what's missing/would-be-different in real prod |
| Stretch (Part 5) | bonus | Any of the above attempted thoughtfully |

We weight the DB-as-dependency piece and the secret-wiring specifically
because that's the part that's easy to fake (hardcode a password) versus
actually understanding Helm's dependency/subchart model — that gap is exactly
what we want to see closed.

## What we're not testing

Real AWS/EKS access, a real container registry, or a real ArgoCD-watched git
remote. Everything should be demonstrable against a local `kind`/minikube
cluster. If something would only make sense against real AWS infra (e.g. an
actual IAM role for a service account, a real ALB ingress), describe what
you'd do rather than trying to fake it.
