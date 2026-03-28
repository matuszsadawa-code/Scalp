from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from core.result import Result


class ShutdownParticipant(Protocol):
    async def stop_new_entries(self) -> Result[None]: ...
    async def cancel_all_orders(self) -> Result[None]: ...
    async def close_connections(self) -> Result[None]: ...
    async def flush(self) -> Result[None]: ...


@dataclass(frozen=True, slots=True)
class ShutdownReport:
    step_results: tuple[str, ...]


async def graceful_shutdown(participant: ShutdownParticipant) -> Result[ShutdownReport]:
    steps: list[str] = []

    for step_name, step_call in (
        ("stop_new_entries", participant.stop_new_entries),
        ("cancel_all_orders", participant.cancel_all_orders),
        ("close_connections", participant.close_connections),
        ("flush", participant.flush),
    ):
        step_result = await step_call()
        if not step_result.ok:
            return Result(error=f"{step_name}_failed:{step_result.error}")
        steps.append(step_name)

    return Result(value=ShutdownReport(step_results=tuple(steps)))
