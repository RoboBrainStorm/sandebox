# server-api Specification

## Purpose

Provides a FastAPI REST control plane to manage the lifecycle of sandboxes, builds, deployments, and administrative monitoring.

## Requirements

### Requirement: Sandbox Lifecycle Management

The server SHALL expose authenticated REST endpoints to create, execute commands in, stream outputs from, and terminate sandboxes.

#### Scenario: Sandbox creation and execution
- **WHEN** an authenticated client sends `POST /sandboxes`
- **THEN** a sandbox session is created and returns the session details
- **AND** `POST /sandboxes/{id}/exec` executes command inside the sandbox returning exit code, stdout, and stderr
