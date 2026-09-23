## Part 1 — Containerize the Application

### What I Built

- Created a **multi-stage Dockerfile** at `app/Dockerfile`.
- Used **`python:3.12-slim`** as the base image.
- Used a separate **builder stage** to create a Python virtual environment and install dependencies.
- Used a separate **runtime stage** containing only the application and required Python environment.
- Configured the runtime container to run as a **non-root `app` user**.
- Exposed application port **8000**.
- Created `app/.dockerignore` to exclude unnecessary files such as Git metadata, virtual environments, caches and local environment files.
- Kept the Docker image configuration independent of the database by supplying database settings through **environment variables**.

### Why I Chose This Approach

- **Multi-stage build:** keeps build-related files and dependencies out of the final runtime image and helps reduce image size.
- **Slim base image:** reduces unnecessary packages and the overall attack surface.
- **Pinned Python version:** avoids unexpected changes that could occur with a `latest` tag and makes builds more reproducible.
- **Non-root user:** The application runs using this user instead of the root user, as it is a major security risk because if a vulnerability is found in the code or its dependencies, an attacker gaining access by exploiting this vulnerability will have root privelages inside the container making it easy to compramise the host system or the K8s cluster.
- **Environment variables:** allows the same image to be used with different database configurations without rebuilding the image.
- **`.dockerignore`:** reduces unnecessary build context and prevents local files from being copied into the image.

### Health Check Decision

- I **did not add a Docker `HEALTHCHECK`**.
- The application already exposes separate `/healthz` and `/readyz` endpoints.
- I decided to use these as **Kubernetes liveness and readiness probes** in Part 2.
- This avoids maintaining two separate health-check mechanisms.
- `/healthz` is used to determine whether the application process is alive.
- `/readyz` is used to determine whether the application is ready to serve traffic, including database availability.
- Also if the PSQL database goes Temporarily down the `/readyz` will fail, if I use docker healthcheck pointing to `/readyz` the orchestrator might kill and restart the container.
- By using the readiness probe the k8s simlpy stops routing traffic to pod untill DB comes back online without restarting perfectly healthy FastAPI process.

### How I Verified It

- Built the Docker image successfully using the application directory as the Docker build context.
- Verified the resulting image using `docker images` and checked that the image was reasonably sized.
- Started PostgreSQL separately in Docker for local testing.
- Started the Notes API container with the required PostgreSQL environment variables.
- Verified the application health endpoint.
- Verified the application readiness endpoint.
- Tested creating a note through the API.
- Tested retrieving notes through the API.

### Problems Faced and How I Solved Them

- Problem: The initial Docker build failed due to a syntax typo in the Dockerfile.
- Solution: Reviewed the Docker build logs, pinpointed the exact line causing the failure, corrected the typo, and successfully rebuilt the image.

### Trade-offs
- I tested the database connection by spinning up a standalone Postgres container and passing environment variables manually, rather than writing a docker-compose.yml file.
- Beacause this was in closer alignment with how k8s works. Manually wiring the isolated API container to the isolated Postgres container perfectly mirrored the deployment strategy needed for Part 2.

### Verification Commands Used

- `docker build`
- `docker images`
- `docker run`
- `curl` for `/healthz`
- `curl` for `/readyz`
- `curl` for creating and retrieving notes

---

## Part 2 — Helm Chart with PostgreSQL Dependency

### What I Built

- Created a Helm chart at **`helm/notes-api/`** for deploying the Notes API.
- Used Helm's generated chart structure as the starting point and customized it for the application instead of rebuilding every template from scratch.
- Added the following application resources:
  - **Deployment**
  - **Service**
  - **ConfigMap**
  - **ServiceAccount**
  - **NOTES.txt**
- Added **PostgreSQL as a Helm chart dependency** using the Bitnami PostgreSQL chart.
- Added separate environment configuration files:
  - **`values-dev.yaml`**
  - **`values-prod.yaml`**
- Added Kubernetes **liveness and readiness probes**.
- Added CPU and memory **resource requests and limits**.
- Added container-level security settings including **non-root execution**, dropped capabilities and a read-only root filesystem.
- Used the generated **`_helpers.tpl`** for consistent resource names and labels.


### Why I Chose This Approach

- **Helm** allows the same k8s application to be packaged and deployed consistently across environments.
- Using a community PostgreSQL chart as a **dependency** avoids writing and maintaining a custom PostgreSQL StatefulSet, Service, Secret and related resources.
- Keeping environment differences in separate values files allows the same chart to be reused for development and production.
- Using Helm's helper templates avoids repeating resource naming and labeling logic throughout the templates.
- Using k8s probes allows k8s to distinguish between an application that is alive and one that is actually ready to serve traffic.
- Resource requests and limits provide predictable scheduling and prevent the application from consuming unlimited cluster resources.

### Helm Chart Structure

- `Chart.yaml`
  - Defines the Notes API chart metadata.
  - Declares the PostgreSQL dependency.
- `values.yaml`
  - Contains the default application configuration.
- `values-dev.yaml`
  - Contains development-specific overrides.
- `values-prod.yaml`
  - Contains production-specific overrides.
- `templates/deployment.yaml`
  - Deploys the Notes API container.
  - Configures environment variables, probes, resources and security context.
- `templates/service.yaml`
  - Exposes the Notes API internally through a Kubernetes ClusterIP Service.
- `templates/configmap.yaml`
  - Stores non-sensitive PostgreSQL configuration.
- `templates/serviceaccount.yaml`
  - Creates the application's ServiceAccount.
- `templates/NOTES.txt`
  - Prints instructions for accessing and testing the deployed API.
- `templates/_helpers.tpl`
  - Provides reusable naming and labeling helpers.
- `charts/`
  - Contains the downloaded PostgreSQL dependency.

### PostgreSQL Dependency

- Declared **Bitnami PostgreSQL** as a chart dependency in `Chart.yaml`.
- Used PostgreSQL chart version **18.8.17**.
- Configured the PostgreSQL dependency through the parent chart's values.
- Configured:
  - Database username: **`notes`**
  - Database name: **`notes`**
  - PostgreSQL architecture: **standalone**
- Used different persistence settings for development and production.

### Why I Used a Subchart

- PostgreSQL is treated as an independently maintained component instead of being implemented as part of the Notes API chart itself.
- The parent chart controls the dependency through values while the PostgreSQL chart manages its own StatefulSet, Services, Secret and storage resources.

### Secret Wiring 

- I did **not** place the PostgreSQL password in the application's `values.yaml`.
- The PostgreSQL dependency generates a k8s Secret.
- The Notes API Deployment reads the application database password from the PostgreSQL-generated Secret using a **`secretKeyRef`**.
- The application uses the Secret's **`password`** key for `POSTGRES_PASSWORD`.
- Non-sensitive database configuration such as:
  - `POSTGRES_HOST`
  - `POSTGRES_PORT`
  - `POSTGRES_DB`
  is stored in the application's ConfigMap.

### Why I Chose This Secret Design

- Prevents duplicating the database password in the parent chart's values.
- Keeps sensitive and non-sensitive configuration separate.
- Demonstrates the intended Helm dependency pattern where the parent application consumes a Secret created by its PostgreSQL subchart.
- This also avoids maintaining two different password values that could become inconsistent.

### Application Configuration

- `POSTGRES_HOST` is generated from the Helm release name and PostgreSQL Service name.
- `POSTGRES_PORT` is set to **5432**.
- `POSTGRES_DB` is taken from the PostgreSQL configuration.
- `POSTGRES_USER` is taken from the PostgreSQL username configuration.
- `POSTGRES_PASSWORD` is obtained from the PostgreSQL Secret.

### Service Configuration

- The Notes API uses a **ClusterIP Service**.
- The Service exposes port **8000**.
- The Service forwards traffic to the application container's HTTP port.
- Service selectors use Helm helper-generated labels to target the Notes API Pods.

### ServiceAccount

- Kept the Helm-generated ServiceAccount template because it already satisfied the application requirement.
- The Deployment references the generated ServiceAccount.

### Probes

- Configured the **liveness probe** to use `/healthz`.
- Configured the **readiness probe** to use `/readyz`.

### Security Configuration

- Configured the application container to run as a **non-root user**.
- Disabled **privilege escalation**.
- Dropped all Linux capabilities.
- Enabled **`readOnlyRootFilesystem`**.
- Configured a numeric `runAsUser` value to allow Kubernetes to verify that the container is running as a non-root user.

### Problem Faced — `CreateContainerConfigError`

- The Docker image defined its runtime user as **`app`**, which is a non-root username.
- k8s was configured with `runAsNonRoot: true`.
- k8s could not verify that the image's username was non-root because it was **non-numeric**.
- The Pod therefore entered `CreateContainerConfigError`.

### Solution

- Checked the numeric UID of the `app` user inside the Docker image.
- Configured the Helm security context with that numeric UID.
- After this change, k8s could verify the non-root configuration and the Notes API Pod started successfully.

### Environment Overrides

#### Development

- **1 Notes API replica**
- Lower CPU and memory allocation
- PostgreSQL persistence disabled for the local development environment

#### Production

- **2 Notes API replicas**
- Higher CPU and memory allocation
- PostgreSQL persistence enabled
- PostgreSQL storage configured to **8 GiB**

### Why the Environments Differ

- Development is intended to be lightweight and temporary.
- Production should provide more application capacity and persistent database storage.
- Keeping the common configuration in `values.yaml` and overriding only environment-specific settings avoids duplicating the entire configuration.

### NOTES.txt

- Added a custom `NOTES.txt` displayed after Helm installation or upgrade.
- It provides:
  - Kubernetes port-forward instructions
  - `/healthz` test
  - `/readyz` test
  - Note creation example
  - Note retrieval example

### Verification Performed

- Built the PostgreSQL chart dependency using **`helm dependency build`**.
- Installed the development release using Helm.
- Verified Pods and Services using **`kubectl get pods,svc`**.
- Used **port-forwarding** to expose the Notes API locally.
- Tested `/healthz`.
- Tested `/readyz`.
- Created a note using the API.
- Retrieved notes from the API.
- Upgraded/installed the production release using the production values file.
- Verified that the production deployment had **2 replicas**.
- Verified that the production PostgreSQL storage claim was **8 GiB and Bound**.
- Ran **`helm lint`** successfully.
- Ran **`helm template`** successfully and inspected the rendered Kubernetes manifests.

### Trade-offs
- Used a **community PostgreSQL Helm chart** instead of managing PostgreSQL resources manually.
- Development PostgreSQL uses temporary storage to keep the local environment lightweight.
- In a real production environment, I would use a dedicated secrets-management solution instead of relying on Kubernetes Secrets alone.
- I would also use a real container registry and environment-specific immutable image tags instead of the local image tag used during Minikube testing.

### Commands Used for Verification

- `helm dependency build helm/notes-api`
- `helm install`
- `helm upgrade --install`
- `kubectl get pods,svc`
- `kubectl get deployment`
- `kubectl get statefulset`
- `kubectl get pvc`
- `kubectl port-forward`
- `curl`
- `helm lint helm/notes-api`
- `helm template`

---

# Part 3 — CI Pipeline (GitHub Actions)
## 1. What I Built

- Added a GitHub Actions workflow at:
  `.github/workflows/ci.yaml`

- The workflow runs on:
  `pull_request`

- The pipeline performs the following checks:

  1. Checkout source code
  2. Set up Python 3.12
  3. Install application dependencies
  4. Run Ruff linting
  5. Build the Docker image
  6. Tag the Docker image using the Git commit SHA
  7. Scan the Docker image using Trivy
  8. Build Helm dependencies
  9. Run `helm lint`
  10. Render Helm manifests
  11. Run Trivy configuration scanning

## 2. Why I Chose This Approach

- I wanted the CI pipeline to catch problems **before a change is merged**.
- The pipeline covers both:
  - **Application-level quality** through Ruff.
  - **Container and Kubernetes security** through Trivy.
- Docker images are built using the **Git commit SHA as the image tag** rather than using a mutable tag such as `latest`.
- Helm templates are rendered during CI so that configuration or templating errors can be detected before deployment.
- Trivy is used as a **security gate**, meaning HIGH and CRITICAL findings can fail the pipeline.

## Python Linting

- Used **Ruff** for Python linting.
- Ruff was selected because it is lightweight and fast, making it suitable for CI.
- The application initially produced several linting findings.
- Some findings were related to:
  - Unused imports.
  - FastAPI dependency injection syntax.
  - Optional type annotation style.
  - Import ordering.
- Removed genuinely unused imports and fixed the import ordering.
- FastAPI-specific findings such as dependency injection were intentionally ignored because they are normal for the framework and changing the application unnecessarily was not required for this assignment.
- Added Ruff configuration in the application's `pyproject.toml`.
- Final local lint check passed successfully.

## Docker Image Build

- Added a CI step to build the Docker image from the application's Dockerfile.
- The image is tagged using the Git commit SHA.
- This provides an immutable reference to the exact source revision that produced the image.
- The CI pipeline therefore does not depend on a mutable `latest` tag.

### Why Use the Git SHA

- `latest` can point to different images over time.
- A Git SHA identifies the exact commit.
- This makes it easier to:
  - Trace an image back to source code.
  - Reproduce a build.
  - Investigate deployment problems.
  - Identify which version was scanned.

## Trivy Image Security Scan

- Added **Trivy** to scan the Docker image after it is built.
- The scan checks for vulnerabilities in the image's packages and dependencies.
- The CI configuration treats:
  - **HIGH**
  - **CRITICAL**
  vulnerabilities as pipeline failures.
- Unfixed vulnerabilities are ignored so that the pipeline focuses on vulnerabilities for which a fix is available.

## Problem Faced — Vulnerabilities in Python Dependencies

- The first Trivy image scan identified HIGH-severity vulnerabilities associated with the application's Python dependency stack.
- The issue was traced to the dependency versions used by FastAPI and its underlying Starlette dependency.
- Instead of ignoring the vulnerabilities, I updated the FastAPI dependency version.
- The CI pipeline was then rerun.
- A later scan still identified vulnerabilities, so the FastAPI version was updated again.
- The dependency was eventually updated to a version that allowed the image vulnerability scan to proceed successfully.

### Why I Fixed the Dependency Instead of Ignoring the Finding

- Ignoring a vulnerability would allow the vulnerable dependency to remain in the image.
- Since the assignment specifically requires a **HIGH/CRITICAL failure gate**, updating the dependency was the more appropriate approach.
- I also avoided installing the changed dependency versions locally because the goal was to validate the final dependency state through the CI pipeline.

## Helm Validation in CI

- The workflow also validates the Helm chart.
- Before linting and rendering, the PostgreSQL chart dependency is built.
- This ensures that the external PostgreSQL dependency required by the parent chart is available during CI.
- Helm lint is then executed against the chart.
- The chart is rendered using the development values file.

## Helm Template Rendering

- The CI pipeline renders the Helm chart into Kubernetes manifests.
- This provides an additional validation layer beyond `helm lint`.
- Rendering helps detect:
  - Invalid Helm expressions.
  - Incorrect values references.
  - Template errors.
  - Missing dependencies.
  - Invalid generated Kubernetes configuration.
- The rendered output is then passed to Trivy for configuration scanning.

## Trivy Kubernetes Configuration Scan

- Added a second Trivy scan using **configuration scanning**.
- Instead of scanning the Docker image, this scan evaluates the rendered Kubernetes configuration.
- This helps identify insecure Kubernetes configuration before deployment.

## Problem Faced — Kubernetes Security Configuration

- The initial Trivy configuration scan reported two HIGH-severity Kubernetes security findings.
- The findings were related to:
  - The container filesystem not being explicitly configured as read-only.
  - The pod/container security configuration not explicitly preventing root execution.

### Solution

- Added `readOnlyRootFilesystem` to the container security configuration.
- Added `runAsNonRoot` to the pod security configuration.
- The application container already runs as a non-root user from the Dockerfile, and the Kubernetes configuration now explicitly enforces the intended security posture as well.
- After correcting the configuration and YAML indentation, the Trivy configuration scan proceeded successfully.

## Trade-offs

- For a production pipeline, the Docker image would normally be pushed to a container registry after successful validation rather than only being built locally inside the CI runner.
- In a larger production environment, I would consider separating the checks into multiple jobs so that:
  - Linting can run independently.
  - Docker build and scanning can run independently.
  - Helm validation can run independently.

---

# Part 4 — GitOps with ArgoCD

## What I Built

- Installed **ArgoCD** on the local Minikube cluster.
- Created separate ArgoCD `Application` resources for:
  - **Development**
  - **Production**
- Both applications point to the GitHub repository containing the Helm chart.
- ArgoCD uses the Helm chart at:
  - `helm/notes-api`
- Development uses:
  - `values-dev.yaml`
- Production uses:
  - `values-prod.yaml`
- The applications deploy into separate k8s namespaces:
  - `notes-dev`
  - `notes-prod`

## Why I Chose This Approach

- Git is treated as the **source of truth** for k8s configuration.
- ArgoCD continuously compares:
  - The desired state defined in Git.
  - The current state running inside k8s.
- This removes the need to manually run Helm commands for every deployment.
- Environment-specific configuration is maintained through separate Helm values files while the same base chart is reused.

## ArgoCD Application — Development

- Created an ArgoCD Application named `notes-api-dev`.
- The application points to the main branch of the GitHub repository.
- It uses the `helm/notes-api` chart.
- The development values file is selected through the ArgoCD Helm configuration.
- The deployment target is the `notes-dev` namespace.
- The namespace can be created automatically through ArgoCD.
- Development is configured with:
  - **Automated synchronization**
  - **Pruning**
  - **Self-healing**

### What This Means

- When the Git repository changes, ArgoCD can automatically synchronize the development environment.
- `prune` allows ArgoCD to remove resources that are no longer part of the desired state.
- `selfHeal` allows ArgoCD to correct changes made directly to the cluster that differ from Git.

## ArgoCD Application — Production

- Created a second ArgoCD Application named `notes-api-prod`.
- It uses the same Helm chart but selects `values-prod.yaml`.
- The deployment target is the `notes-prod` namespace.
- Production was intentionally configured for **manual synchronization**.

### Why Production Uses Manual Sync

- Development changes can be deployed automatically for faster iteration.
- Production changes require an explicit synchronization step.
- This provides an additional review point before production is changed.
- Git still remains the desired-state source, but deployment is not automatically applied immediately after every Git change.

## Problem Faced — ArgoCD ImagePullBackOff

- After installation, some ArgoCD pods entered `ImagePullBackOff`.
- The problem was not caused by the Kubernetes manifests.
- Investigation showed that the Minikube environment had difficulty reaching external container registries directly.
- Network connectivity was tested from:
  - WSL
  - Docker containers
  - Minikube
- The external registry was reachable through the Docker Desktop proxy path.

### Solution

- Investigated the Docker Desktop proxy configuration.
- Verified that HTTPS access through the proxy worked.
- ArgoCD images were subsequently pulled successfully.
- Once the images were available, the ArgoCD components became healthy.

## Development GitOps Verification

- Verified that ArgoCD created the `notes-dev` namespace.
- Verified that the following workloads were running:
  - Notes API
  - PostgreSQL
- Verified that the API service was created correctly.
- Used port-forwarding to access the service locally.
- Tested:
  - `/healthz`
  - `/readyz`
  - Creating a note
  - Listing notes
- The application worked successfully after being deployed through ArgoCD.

## Problem Faced — Production Application Manifest

- The first production ArgoCD Application manifest placed `syncOptions` at the wrong level in the specification.
- ArgoCD rejected the manifest because the structure did not match the expected Application schema.

### Solution

- Moved `syncOptions` under the correct `syncPolicy` section.
- The Application was then accepted by ArgoCD.

## Production GitOps Verification

- Verified that production contains:
  - **2 Notes API replicas**
  - **1 PostgreSQL instance**
- Verified that the production PostgreSQL storage configuration was applied.
- Port-forwarded the production service for local testing.
- Tested:
  - `/healthz`
  - `/readyz`
  - Creating a note
  - Listing notes
- The production deployment worked successfully.

## GitOps Deployment Flow

The intended deployment flow is:

**Developer change**

→ Change Helm chart or environment values in Git

→ Pull request and CI validation

→ Merge into the main branch

→ ArgoCD detects the changed Git state

→ ArgoCD fetches the updated repository

→ Helm chart is rendered with the selected environment values

→ ArgoCD compares desired state with live Kubernetes state

→ Synchronization occurs

→ Kubernetes applies the changed resources

→ Deployment creates a new ReplicaSet when required

→ New Pods are created

→ Readiness/liveness checks determine application health

→ ArgoCD reports the final sync and health status

## What Happens When `values-prod.yaml` Changes

- Suppose a production value such as:
  - Replica count
  - CPU/memory resources
  - PostgreSQL storage
  - Environment configuration
  
  is changed in `values-prod.yaml`.

- After the change is merged into the main branch:
  - ArgoCD detects that the Git repository differs from the currently deployed state.
  - The production Application becomes **OutOfSync**.
  - Because production uses manual synchronization, the updated desired state is not immediately applied.
  - After an explicit synchronization, ArgoCD renders the Helm chart using the updated production values.
  - Kubernetes receives the changed manifests.
  - If the Deployment specification changed, Kubernetes performs the required rollout.
  - ArgoCD monitors the rollout and reports whether the resources become healthy.

## Verification Performed

- Verified that ArgoCD is running correctly in Minikube.
- Verified that ArgoCD can access the Git repository.
- Verified the development Application.
- Verified automated development synchronization.
- Verified development application health.
- Verified development API functionality.
- Verified the production Application.
- Verified manual production synchronization.
- Verified production application health.
- Verified production API functionality.
- Verified different Helm values are applied to development and production.
- Verified that ArgoCD-managed resources remain in the expected namespaces.

## Trade-offs 

- For the local exercise, ArgoCD was installed directly into Minikube.

---