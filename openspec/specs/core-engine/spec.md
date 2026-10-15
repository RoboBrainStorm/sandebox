# core-engine Specification

## Purpose

Provides Kubernetes pod and job execution primitives with gVisor (`runsc`) kernel isolation and container specification building.

## Requirements

### Requirement: Hardened gVisor Pod Execution

The core engine SHALL construct Kubernetes Pod and Job manifests enforcing the `gvisor` RuntimeClass and security context constraints to isolate untrusted agent workloads.

#### Scenario: Pod specification includes runtimeClass and security context
- **WHEN** a sandbox pod specification is generated
- **THEN** `runtimeClassName` is set to `gvisor` (or user-configured class)
- **AND** container security contexts drop unnecessary Linux capabilities

### Requirement: Deterministic Container Naming

The system SHALL derive RFC-1123 compliant, deterministic Kubernetes resource names for sandbox pods and services.

#### Scenario: Valid Kubernetes resource name derivation
- **WHEN** given a session identity with mixed-case or long strings
- **THEN** the derived name starts with `rb-sbx-` (or `rb-srv-`)
- **AND** the name is lowercase and does not exceed 63 characters
