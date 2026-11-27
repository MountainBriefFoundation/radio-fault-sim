"""Deterministic, in-process queue, PTT-line, and feedback fault model."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class WriteMode(str, Enum):
    NORMAL = "normal"
    DOWN = "down"
    FAILED = "failed"
    OCCUPIED = "occupied"
    PARTIAL = "partial"


class FeedbackMode(str, Enum):
    FOLLOW = "follow"
    UNAVAILABLE = "unavailable"
    FALSE_OFF = "false_off"
    FALSE_ON = "false_on"


@dataclass(frozen=True)
class Faults:
    """Fault configuration; replace it with ``set_faults`` during a scenario."""

    write_mode: WriteMode = WriteMode.NORMAL
    feedback_mode: FeedbackMode = FeedbackMode.FOLLOW
    cancel_honored: bool = True
    release_honored: bool = True
    release_lies: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.write_mode, WriteMode):
            raise TypeError("write_mode must be a WriteMode")
        if not isinstance(self.feedback_mode, FeedbackMode):
            raise TypeError("feedback_mode must be a FeedbackMode")
        for name in ("cancel_honored", "release_honored", "release_lies"):
            if type(getattr(self, name)) is not bool:
                raise TypeError(f"{name} must be a bool")


@dataclass(frozen=True)
class Snapshot:
    mono_ms: int
    alive: bool
    queued: bool
    partial: bool
    payload_bytes: int
    queued_mono_ms: int | None
    keyed_mono_ms: int | None
    ptt_line: bool
    feedback: str
    writes_accepted: int
    contention_seen: bool


class PartialWriteError(ConnectionError):
    """A simulated short write left a one-byte prefix in the queue."""

    def __init__(self, accepted_bytes: int, requested_bytes: int) -> None:
        self.accepted_bytes = accepted_bytes
        self.requested_bytes = requested_bytes
        super().__init__(f"short write: {accepted_bytes} of {requested_bytes} bytes queued")


def _integer(value: int, name: str, *, minimum: int = 0) -> int:
    if type(value) is not int:
        raise TypeError(f"{name} must be an integer")
    if value < minimum:
        raise ValueError(f"{name} must be at least {minimum}")
    return value


def _owner(value: str) -> str:
    if not isinstance(value, str):
        raise TypeError("owner must be a string")
    if not 1 <= len(value) <= 128 or not value.strip():
        raise ValueError("owner must contain 1 to 128 characters and not be blank")
    return value


class SimTnc:
    """One queue and one modeled PTT line driven by caller-supplied time.

    ``write`` advances an existing transmission, then queues the new bytes.
    Call ``advance`` to process the new frame's key-up and completion edges.
    Untimed commands operate at the most recently supplied timestamp. This
    object models state only; it opens no devices, sockets, or audio streams.
    """

    def __init__(
        self,
        *,
        queue_delay_ms: int = 0,
        ptt_duration_ms: int = 1000,
        feedback_delay_ms: int = 0,
        max_payload_bytes: int = 4096,
        faults: Faults | None = None,
    ) -> None:
        self._queue_delay_ms = _integer(queue_delay_ms, "queue_delay_ms")
        self._ptt_duration_ms = _integer(ptt_duration_ms, "ptt_duration_ms", minimum=1)
        self._feedback_delay_ms = _integer(feedback_delay_ms, "feedback_delay_ms")
        self._max_payload_bytes = _integer(max_payload_bytes, "max_payload_bytes", minimum=1)
        if faults is not None and not isinstance(faults, Faults):
            raise TypeError("faults must be a Faults object")
        self._faults = faults if faults is not None else Faults()
        self._owner: str | None = None
        self._payload: bytes | None = None
        self._partial = False
        self._queued_ms: int | None = None
        self._keyed_ms: int | None = None
        self._now_ms = 0
        self._ptt_line = False
        self._alive = True
        self._writes_accepted = 0
        self._contention_seen = False

    @property
    def faults(self) -> Faults:
        return self._faults

    def set_faults(self, faults: Faults) -> Snapshot:
        """Change faults at the current timestamp without advancing time."""
        if not isinstance(faults, Faults):
            raise TypeError("faults must be a Faults object")
        self._faults = faults
        return self.snapshot()

    def attach(self, owner: str) -> None:
        owner = _owner(owner)
        if self._owner is not None:
            raise RuntimeError("queue owner already set")
        self._owner = owner

    def write(self, owner: str, payload: bytes | bytearray, mono_ms: int) -> None:
        owner = _owner(owner)
        if not isinstance(payload, (bytes, bytearray)):
            raise TypeError("payload must be bytes or bytearray")
        if not 1 <= len(payload) <= self._max_payload_bytes:
            raise ValueError("payload length is outside the configured limit")
        if self._faults.write_mode is WriteMode.PARTIAL and len(payload) < 2:
            raise ValueError("the partial-write fault requires at least two bytes")
        self.advance(mono_ms)
        mode = self._faults.write_mode
        if not self._alive or mode is WriteMode.DOWN:
            raise ConnectionError("simulated TNC is down")
        if owner != self._owner:
            self._contention_seen = True
            raise RuntimeError("queue ownership conflict")
        if mode is WriteMode.FAILED:
            raise ConnectionError("simulated write failed")
        if self._payload is not None or mode is WriteMode.OCCUPIED:
            raise RuntimeError("simulated queue is full")
        self._payload = bytes(payload[:1] if mode is WriteMode.PARTIAL else payload)
        self._partial = mode is WriteMode.PARTIAL
        self._queued_ms = self._now_ms
        self._keyed_ms = None
        if self._partial:
            raise PartialWriteError(len(self._payload), len(payload))
        self._writes_accepted += 1

    def advance(self, mono_ms: int) -> Snapshot:
        """Settle due transitions, including a whole pulse crossed in one step.

        A coarse step does not record transient edges. A crashed controller
        freezes the modeled line; this is one chosen failure model, not a
        statement about all real TNCs.
        """
        mono_ms = _integer(mono_ms, "mono_ms")
        if mono_ms < self._now_ms:
            raise ValueError("monotonic time cannot move backwards")
        self._now_ms = mono_ms
        if self._alive and self._payload is not None and self._queued_ms is not None:
            if self._keyed_ms is None and mono_ms >= self._queued_ms + self._queue_delay_ms:
                self._keyed_ms = self._queued_ms + self._queue_delay_ms
                self._ptt_line = True
            if (
                self._keyed_ms is not None
                and self._faults.release_honored
                and mono_ms >= self._keyed_ms + self._ptt_duration_ms
            ):
                self._idle_off()
        return self.snapshot()

    def cancel(self, owner: str) -> bool:
        """Cancel an unkeyed queue; a partial prefix is also queued data."""
        owner = _owner(owner)
        if (
            not self._alive
            or owner != self._owner
            or self._ptt_line
            or self._keyed_ms is not None
            or not self._faults.cancel_honored
        ):
            return False
        self._idle_off()
        return True

    def force_off(self) -> bool:
        """Return the command acknowledgment, which can disagree with state."""
        if not self._alive or not self._faults.release_honored:
            return False
        if self._faults.release_lies:
            return True
        self._idle_off()
        return True

    def crash(self) -> Snapshot:
        """Freeze the controller, retaining its queue and modeled line state."""
        self._alive = False
        return self.snapshot()

    def snapshot(self) -> Snapshot:
        mode = self._faults.feedback_mode
        if mode is FeedbackMode.UNAVAILABLE:
            feedback = "lost"
        elif mode is FeedbackMode.FALSE_OFF:
            feedback = "off"
        elif mode is FeedbackMode.FALSE_ON:
            feedback = "on"
        elif not self._ptt_line:
            feedback = "off"
        elif self._keyed_ms is not None and self._now_ms < self._keyed_ms + self._feedback_delay_ms:
            feedback = "off"
        else:
            feedback = "on"
        return Snapshot(
            mono_ms=self._now_ms,
            alive=self._alive,
            queued=self._payload is not None,
            partial=self._partial,
            payload_bytes=len(self._payload) if self._payload is not None else 0,
            queued_mono_ms=self._queued_ms,
            keyed_mono_ms=self._keyed_ms,
            ptt_line=self._ptt_line,
            feedback=feedback,
            writes_accepted=self._writes_accepted,
            contention_seen=self._contention_seen,
        )

    def _idle_off(self) -> None:
        self._ptt_line = False
        self._payload = None
        self._partial = False
        self._queued_ms = None
        self._keyed_ms = None
