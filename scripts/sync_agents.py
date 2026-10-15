#!/usr/bin/env python3
"""Synchronize AI assistant entrypoints from AGENTS.md."""

import re
import sys
from pathlib import Path


def main() -> None:
    root_dir = Path(__file__).resolve().parent.parent
    agents_path = root_dir / "AGENTS.md"

    if not agents_path.exists():
        print("Error: AGENTS.md not found.", file=sys.stderr)
        sys.exit(1)

    agents_content = agents_path.read_text(encoding="utf-8")

    # Extract the critical invariants block
    match = re.search(
        r"(> ⚠️ CRITICAL INVARIANTS[\s\S]*?)(?=\n\nThis file documents)", agents_content
    )
    if not match:
        print(
            "Error: Could not locate CRITICAL INVARIANTS in AGENTS.md", file=sys.stderr
        )
        sys.exit(1)

    invariants = match.group(1).strip()

    generated_content = f"""# Sandebox AI Assistant Directives

{invariants}

---

## Authority & Deep Documentation

**Follow [AGENTS.md](AGENTS.md) — the single authority** for workflow, Gitflow branching, the Feature-First doc strategy, component boundaries, and testing commands.

- Canonical Directives & Workflow: [AGENTS.md](AGENTS.md)
- Architecture & Quickstart: [README.md](README.md)
- OpenSpec Specifications: [openspec/specs/](openspec/specs/)
- Active Changes: [openspec/changes/](openspec/changes/)
"""

    targets = ["CLAUDE.md", "GEMINI.md", ".cursorrules"]
    for target in targets:
        target_path = root_dir / target
        target_path.write_text(generated_content, encoding="utf-8")

    print(f"✓ Synchronized {', '.join(targets)} from AGENTS.md.")


if __name__ == "__main__":
    main()
