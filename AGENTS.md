# Developer Workflow & Protocol (AGENTS.md)

> ⚠️ CRITICAL INVARIANTS (Do not violate):
1. REPO BOUNDARIES & IDENTITY:
   - Sandebox is an independent, MIT-licensed open-source project (`github.com/RoboBrainStorm/sandebox`).
   - It is a self-hostable sandbox environment for agents running untrusted code on Kubernetes with gVisor (`runsc`) and Knative scale-to-zero.
   - It MUST remain completely decoupled from proprietary RoboBrainstorm backend logic, database models, or billing systems.
2. PACKAGE BOUNDARIES:
   - `core/`: Standalone execution engine (`sandebox-core`) for Kubernetes pod/job management, container building, and gVisor isolation.
   - `server/`: FastAPI control-plane service (`sandebox-server`) exposing REST APIs for sandboxes, builds, deployments, and admin actions.
   - `cli/`: Python CLI tool (`sandebox`) for diagnosis, running sandboxes, and cluster validation.
   - `sdk/python/`: Python client library (`sandebox`).
   - `sdk/typescript/`: TypeScript client library (`@sandebox/sdk`).
   - `admin/`: Vite + React web panel for observability (sandboxes, logs, resource usage).
   - `deploy/helm/`: Helm charts (`sandebox` control plane and workload pods).
3. FEATURE-FIRST (OpenSpec):
   - Every non-trivial change MUST use an OpenSpec change (`openspec new change <name>` or `/opsx-propose`).
   - Specs live in `openspec/specs/`. Active changes live in `openspec/changes/`.
4. CONVENTIONAL COMMITS & GITFLOW:
   - Trunk branches: `main` (stable releases) and `dev` (development integration).
   - Working branches: `change/{change-name}` or `bugfix/{name}` off `dev`.
   - All commits follow Conventional Commits: `feat`, `fix`, `docs`, `chore`, `refactor`, `test`, `ci`.
5. CANONICAL END-OF-CHANGE FLOW:
   - When an OpenSpec change is complete and archived via `/opsx-archive`:
     1. Commit the archive move
     2. Push branch to `origin change/{change-name}`
     3. Create Pull Request targeting `dev` (`gh pr create --base dev`)
     4. Switch back to `dev` branch (`git checkout dev`)
6. MONOREPO ARCHITECTURE & VERIFICATION (Turborepo):
   - Sandebox is managed as a polyglot Turborepo with pnpm workspaces.
   - Full gate: `pnpm run check:all` (OpenSpec + Turbo test + Turbo lint)
   - Monorepo Build: `pnpm run build`
   - Monorepo Test: `pnpm run test`
   - Monorepo Lint: `pnpm run lint`
   - OpenSpec Validation: `openspec validate --all`
   - Python unit & substrate tests: `pnpm run test:python`

This file documents the protocol for both human and AI developers. **It is the single authority.**
`CLAUDE.md`, `GEMINI.md`, and `.cursorrules` are synchronized entrypoints generated from this file.

---

## 1. Development Workflow (Gitflow + OpenSpec)

We follow a **Gitflow** branching model integrated with our **Feature-First** specification strategy.

### Branching Strategy

| You are on | Work type | Branch name | Target (PR into) |
| :--- | :--- | :--- | :--- |
| `dev` | OpenSpec change | `change/{change-name}` | `dev` |
| `dev` | Untracked bug fix | `bugfix/{name}` | `dev` |
| `main` | Production hotfix | `hotfix/{name}` | `main`, then back-merged to `dev` |

*Rules:*
- **`feature/*` branches are forbidden.** Use `change/{change-name}` off `dev`.
- Promotion flows: `change/* → dev → (stabilization / release tag) → main`.

### The 3-Step OpenSpec Loop

1. **Plan (`/opsx-propose <name>`)**: Scaffolds the change and generates proposal, specs, design, and tasks in one step.
2. **Implement (`/opsx-apply`)**: Implements code across packages, following TDD and writing tests alongside features.
3. **Archive & Ship (`/opsx-archive`)**: Syncs delta specs, moves change to `archive/`, pushes the branch, opens a PR into `dev`, and switches back to `dev`.

---

## 2. Testing & Verification

Every change MUST pass verification before opening a Pull Request:

```bash
# 1. Run all unit and mock tests across core, server, and substrate
PYTHONPATH=core/src:server/src uv run --python 3.12 \
  --with pytest --with pytest-asyncio --with pytest-mock \
  --with structlog --with httpx --with fastapi --with pydantic \
  --with kubernetes --with kubernetes_asyncio \
  pytest tests/ core/tests/ server/tests/ -v

# 2. Code style and linting
uv run ruff check .
uv run ruff format --check .

# 3. OpenSpec validation
openspec validate --all
```

Integration tests requiring a live Minikube / Kubernetes cluster (`@pytest.mark.integration`) are skipped automatically when no cluster is reachable and can be run explicitly with a local cluster active.

---

## 3. Synchronizing Directives

To synchronize `CLAUDE.md`, `GEMINI.md`, and `.cursorrules` from `AGENTS.md`:

```bash
python3 scripts/sync_agents.py
```
