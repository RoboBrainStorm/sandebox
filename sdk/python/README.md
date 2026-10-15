# sandebox Python SDK

Client library for interacting with the `sandebox` control-plane API.

## Installation

```bash
pip install sandebox
```

## Usage

```python
import asyncio
from sandebox import AsyncSandboxClient


async def main():
    client = AsyncSandboxClient(base_url="http://localhost:8000", api_key="sk-sbx-...")
    session = await client.create_sandbox(image="python:3.12-slim")
    print(f"Created sandbox session: {session.session_id}")

    res = await session.exec("python -c 'print(\"Hello world!\")'")
    print(res.stdout)

    await session.stop()


asyncio.run(main())
```
