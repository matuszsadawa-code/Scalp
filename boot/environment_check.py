from __future__ import annotations

import platform
import sys
from dataclasses import dataclass

from core.result import Result


@dataclass(frozen=True, slots=True)
class EnvironmentSnapshot:
    python_version: str
    platform_name: str


def check_runtime() -> Result[EnvironmentSnapshot]:
    if sys.version_info < (3, 12):
        return Result(error="python>=3.12 is required")

    return Result(
        value=EnvironmentSnapshot(
            python_version=sys.version.split()[0],
            platform_name=platform.platform(),
        )
    )
