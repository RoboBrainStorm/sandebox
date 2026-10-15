# Sandebox

> **The self-hostable sandbox environment for your agents.**

Open-source, self-hosted execution substrate for running untrusted AI agent code on Kubernetes with gVisor kernel isolation and Knative scale-to-zero scheduling.

## Features

- **Hardened Isolation**: Built exclusively for gVisor (`runsc`), ensuring containerized processes cannot breach kernel boundaries.
- **On-Demand Elasticity**: Knative-scheduled sandbox lifecycle with scale-to-zero capabilities.
- **REST Control Plane**: FastAPI server exposing endpoints for creating, executing, streaming, and terminating sandboxes.
- **Multi-Language SDKs**: Python (`sandebox`) and TypeScript (`@sandebox/sdk`) clients.
- **Observability Admin Panel**: Lightweight web dashboard for viewing active sandboxes, logs, and resource usage.
- **Helm-Ready**: Deploy to any Kubernetes cluster with a single `helm install`.

## Architecture

```
sandebox/
├── core/             # Standalone execution engine (k8s client, container builder, gVisor runner)
├── server/           # FastAPI control-plane API
├── sdk/              # Python & TypeScript client SDKs
├── admin/            # Observability web panel
├── cli/              # sandebox CLI (doctor, validate, run)
└── deploy/helm/      # Helm charts (sandebox control plane + sandbox-pod workload)
```

## Prerequisites

1. **Kubernetes Cluster** (v1.28+)
2. **gVisor (`runsc`)**: A `RuntimeClass` named `gvisor` must be installed on your cluster nodes.
3. **Knative Serving** (v1.12+)

## Quickstart: Helm Installation

Install `sandebox` into your cluster:

```bash
helm repo add sandebox https://charts.sandebox.org
helm repo update

helm install sandebox ./deploy/helm/sandebox \
  --namespace sandebox-system \
  --create-namespace \
  --set runtimeClass=gvisor
```

Once installed, follow the notes printed by Helm to obtain the control plane URL and administrative API key.

## CLI Usage

Verify your cluster setup with the `sandebox` CLI:

```bash
sandebox doctor
```

Run a test sandbox:

```bash
sandebox run --image python:3.12-slim --command "python -c 'print(\"Hello from gVisor sandbox!\")'"
```

## Python SDK Example

```python
from sandebox import SandboxClient

client = SandboxClient(
    base_url="http://sandebox.sandebox-system.svc.cluster.local", api_key="sk-..."
)

session = client.create_sandbox(image="python:3.12-slim")
result = session.exec(["python", "-c", "import sys; print(sys.version)"])
print(result.stdout)
session.stop()
```

## License

MIT License. See [LICENSE](./LICENSE).
