from __future__ import annotations

import argparse
import asyncio
import os
import sys

from core.config import SandboxConfig
from core.kubernetes.client import get_k8s_client, close_k8s_client


async def run_doctor(args: argparse.Namespace) -> int:
    config = SandboxConfig.from_env()
    print("==================================================")
    print(" sandebox doctor: Environment & Cluster Check")
    print("==================================================")

    overall_ok = True

    # 1. Kubernetes Connectivity
    print("\n[1/3] Checking Kubernetes API connectivity...")
    try:
        api_client = await get_k8s_client()
        from kubernetes_asyncio import client
        core_v1 = client.CoreV1Api(api_client)
        ns_list = await core_v1.list_namespace(limit=1)
        print("  ✓ Connected to Kubernetes API successfully.")
    except Exception as exc:
        print(f"  ✗ Failed to reach Kubernetes API: {exc}")
        overall_ok = False
        api_client = None

    # 2. Check RuntimeClass (gVisor)
    print(f"\n[2/3] Checking RuntimeClass '{config.runtime_class}'...")
    if api_client:
        try:
            from kubernetes_asyncio import client
            node_v1 = client.NodeV1Api(api_client)
            rc_list = await node_v1.list_runtime_class()
            classes = [rc.metadata.name for rc in rc_list.items]
            if config.runtime_class in classes:
                print(f"  ✓ RuntimeClass '{config.runtime_class}' found in cluster.")
            else:
                print(f"  ✗ RuntimeClass '{config.runtime_class}' NOT found in cluster! Available classes: {classes or 'none'}")
                print(f"    gVisor (runsc) is required for sandebox isolation. Please install the gVisor RuntimeClass.")
                overall_ok = False
        except Exception as exc:
            print(f"  ✗ Failed to query RuntimeClasses: {exc}")
            overall_ok = False
    else:
        print("  - Skipped (no cluster connection).")

    # 3. Check Knative Serving CRDs
    print("\n[3/3] Checking Knative Serving CRDs...")
    if api_client:
        try:
            from kubernetes_asyncio import client
            custom = client.CustomObjectsApi(api_client)
            await custom.list_namespaced_custom_object(
                group="serving.knative.dev",
                version="v1",
                namespace=config.namespace,
                plural="services",
                limit=1,
            )
            print("  ✓ Knative Serving CRDs verified.")
        except Exception as exc:
            err_msg = str(exc)
            if "Not Found" in err_msg or "404" in err_msg:
                print("  ✗ Knative Serving CRD 'services.serving.knative.dev' not found. Is Knative installed?")
                overall_ok = False
            else:
                # Namespace might not exist yet, but CRD itself exists
                print(f"  ✓ Knative Serving API responsive ({exc}).")
    else:
        print("  - Skipped (no cluster connection).")

    if api_client:
        await close_k8s_client()

    print("\n--------------------------------------------------")
    if overall_ok:
        print("RESULT: All cluster and runtime requirements satisfied! ✓")
        return 0
    else:
        print("RESULT: Diagnostic issues identified above. Please resolve before deployment.")
        return 1


def run_validate(args: argparse.Namespace) -> int:
    config = SandboxConfig.from_env()
    print("Validating sandebox configuration:")
    print(f"  Namespace:           {config.namespace}")
    print(f"  Default Image:       {config.image}")
    print(f"  Runtime Class:       {config.runtime_class}")
    print(f"  CPU Limit:           {config.cpu_limit}")
    print(f"  Memory Limit:        {config.memory_limit}")
    print(f"  Registry (Push):     {config.model_registry_push}")
    print(f"  Registry (Pull):     {config.model_registry_pull}")
    print(f"  BuildKit Addr:       {config.buildkit_addr}")
    print("\nConfiguration structure is valid! ✓")
    return 0


async def run_workload(args: argparse.Namespace) -> int:
    server_url = getattr(args, "server_url", None)
    if server_url:
        from sandebox import AsyncSandboxClient
        print(f"Running via sandebox server at {server_url}...")
        client = AsyncSandboxClient(base_url=server_url, api_key=getattr(args, "api_key", None))
        try:
            if args.code:
                res = await client.run_python(args.code)
            else:
                res = await client.run_command(args.command or "echo 'Hello from sandebox'")
            print("STDOUT:\n" + res.stdout)
            if res.stderr:
                print("STDERR:\n" + res.stderr)
            return res.exit_code
        finally:
            await client.close()
    else:
        from core.provider import KnativeProvider
        print("Running directly via core engine...")
        provider = KnativeProvider()
        if args.code:
            res = await provider.run_python(args.code)
        else:
            res = await provider.run_command(args.command or "echo 'Hello from sandebox'")
        print("STDOUT:\n" + res.stdout)
        if res.stderr:
            print("STDERR:\n" + res.stderr)
        return res.exit_code


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="sandebox",
        description="CLI utility for sandebox diagnosis and workload execution",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # doctor
    subparsers.add_parser("doctor", help="Check Kubernetes connectivity and gVisor RuntimeClass")

    # validate
    subparsers.add_parser("validate", help="Validate runtime configuration")

    # run
    run_parser = subparsers.add_parser("run", help="Run a one-shot command or code snippet in a sandbox")
    run_parser.add_argument("--command", "-c", type=str, default=None, help="Shell command to run")
    run_parser.add_argument("--code", type=str, default=None, help="Python code to run")
    run_parser.add_argument("--server-url", type=str, default=None, help="Optional sandebox server URL")
    run_parser.add_argument("--api-key", type=str, default=None, help="API key for server")

    parsed = parser.parse_args()

    if parsed.command == "doctor":
        rc = asyncio.run(run_doctor(parsed))
        sys.exit(rc)
    elif parsed.command == "validate":
        rc = run_validate(parsed)
        sys.exit(rc)
    elif parsed.command == "run":
        rc = asyncio.run(run_workload(parsed))
        sys.exit(rc)


if __name__ == "__main__":
    main()
