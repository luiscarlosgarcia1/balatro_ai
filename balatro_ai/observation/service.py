from __future__ import annotations

from datetime import datetime, timezone

from ..models import GameObservation, ObservationPayload
from .capture import LightweightCapturePlan
from .canonical import serialize_observation
from .live_parser import LiveObservationParser
from .paths import BalatroPaths
from .save_decoder import SavePayloadDecoder, SaveSnapshot
from .save_parser import SaveObservationParser


class BalatroSaveObserver:
    """Observation layer that prefers live save files over OCR-heavy screenshots."""

    def __init__(
        self,
        paths: BalatroPaths | None = None,
        decoder: SavePayloadDecoder | None = None,
        capture_plan: LightweightCapturePlan | None = None,
        live_parser: LiveObservationParser | None = None,
        save_parser: SaveObservationParser | None = None,
    ) -> None:
        self.paths = paths or BalatroPaths()
        self.decoder = decoder or SavePayloadDecoder()
        self.capture_plan = capture_plan or LightweightCapturePlan.default()
        self.live_parser = live_parser or LiveObservationParser()
        self.save_parser = save_parser or SaveObservationParser()

    def observe(self) -> ObservationPayload:
        live_observation = self.read_live_observation()
        if live_observation is not None:
            return serialize_observation(live_observation)

        snapshot = self.read_snapshot()
        return serialize_observation(self.save_parser.parse_snapshot(snapshot))

    def read_live_observation(self) -> GameObservation | None:
        return self.live_parser.parse_file(self.paths.live_state_path)

    def read_snapshot(self) -> SaveSnapshot:
        raw_payload = self.decoder.decode_file(self.paths.save_path)
        modified_at = datetime.fromtimestamp(
            self.paths.save_path.stat().st_mtime,
            tz=timezone.utc,
        )
        return SaveSnapshot(
            profile=self.paths.profile,
            save_path=self.paths.save_path,
            modified_at=modified_at,
            raw_payload=raw_payload,
            active_payload=self.decoder.extract_active_payload(raw_payload),
        )
