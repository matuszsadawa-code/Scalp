from __future__ import annotations

import asyncio
from pathlib import Path

from boot.environment_check import check_runtime
from config.loader import load_app_config


async def main() -> int:
    runtime = check_runtime()
    if not runtime.ok:
        print(f"startup_error: {runtime.error}")
        return 1

    config_result = load_app_config(Path("config/base.yaml"))
    if not config_result.ok:
        print(f"config_error: {config_result.error}")
        return 1

    assert runtime.value is not None
    assert config_result.value is not None
    print(
        "boot_ok",
        {
            "python": runtime.value.python_version,
            "platform": runtime.value.platform_name,
            "config_version": config_result.value.config_version,
            "symbols": config_result.value.system.symbols,
        },
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
