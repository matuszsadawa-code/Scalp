from __future__ import annotations

from dataclasses import dataclass

from core.result import Result


@dataclass(frozen=True, slots=True)
class BinanceDepthEventIds:
    first_update_id: int
    final_update_id: int
    previous_final_update_id: int


@dataclass(slots=True)
class BinanceDepthSync:
    previous_final_update_id: int | None = None

    def seed_from_snapshot(self, snapshot_last_update_id: int) -> None:
        self.previous_final_update_id = snapshot_last_update_id

    def validate(self, ids: BinanceDepthEventIds) -> Result[None]:
        if self.previous_final_update_id is None:
            return Result(error="snapshot_not_seeded")

        if ids.previous_final_update_id != self.previous_final_update_id:
            self.previous_final_update_id = None
            return Result(error="sequence_gap_resync_required")

        if ids.first_update_id > ids.final_update_id:
            self.previous_final_update_id = None
            return Result(error="invalid_update_range")

        self.previous_final_update_id = ids.final_update_id
        return Result(value=None)
