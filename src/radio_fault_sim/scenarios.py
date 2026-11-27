"""Small synthetic scenarios shared by the CLI and automated checks."""

from __future__ import annotations

from dataclasses import asdict

from .model import Faults, FeedbackMode, PartialWriteError, SimTnc, WriteMode


SCENARIOS = (
    "normal",
    "partial-write",
    "stuck-ptt",
    "crash-latched",
    "feedback-lost",
    "feedback-false-off",
    "release-lies",
    "ownership-conflict",
    "coarse-clock",
)


def run_scenario(name: str) -> dict:
    if name not in SCENARIOS:
        raise ValueError("unknown scenario")
    faults = {
        "partial-write": Faults(write_mode=WriteMode.PARTIAL),
        "stuck-ptt": Faults(release_honored=False),
        "feedback-lost": Faults(feedback_mode=FeedbackMode.UNAVAILABLE),
        "feedback-false-off": Faults(feedback_mode=FeedbackMode.FALSE_OFF),
        "release-lies": Faults(release_lies=True),
    }.get(name, Faults())
    sim = SimTnc(queue_delay_ms=100, ptt_duration_ms=300, faults=faults)
    sim.attach("controller-a")
    rows: list[dict] = []

    def record(label: str) -> None:
        rows.append({"label": label, **asdict(sim.snapshot())})

    outcomes: dict = {}
    try:
        sim.write("controller-a", b"synthetic packet", mono_ms=0)
    except PartialWriteError as error:
        outcomes["short_write_bytes"] = error.accepted_bytes
    record("after-write")
    if name == "partial-write":
        outcomes["cancel_acknowledged"] = sim.cancel("controller-a")
        record("after-cancel")
    elif name == "coarse-clock":
        sim.advance(2000)
        record("after-coarse-step")
    elif name == "ownership-conflict":
        try:
            sim.write("controller-b", b"another synthetic packet", mono_ms=1)
        except RuntimeError:
            outcomes["second_owner_rejected"] = True
        record("after-conflict")
    else:
        sim.advance(99)
        record("before-key-up")
        sim.advance(100)
        record("after-key-up")
        if name == "crash-latched":
            sim.crash()
            record("after-crash")
        if name == "release-lies":
            outcomes["release_acknowledged"] = sim.force_off()
            record("after-release-command")
        sim.advance(400)
        record("at-planned-completion")
        if name in ("stuck-ptt", "crash-latched"):
            outcomes["release_acknowledged"] = sim.force_off()
            record("after-release-command")
    return {"scenario": name, "outcomes": outcomes, "samples": rows}
