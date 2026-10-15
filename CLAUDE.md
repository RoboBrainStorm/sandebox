# Sandebox AI Assistant Directives

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

---

## Authority & Deep Documentation

**Follow [AGENTS.md](AGENTS.md) — the single authority** for workflow, Gitflow branching, the Feature-First doc strategy, component boundaries, and testing commands.

- Canonical Directives & Workflow: [AGENTS.md](AGENTS.md)
- Architecture & Quickstart: [README.md](README.md)
- OpenSpec Specifications: [openspec/specs/](openspec/specs/)
- Active Changes: [openspec/changes/](openspec/changes/)
