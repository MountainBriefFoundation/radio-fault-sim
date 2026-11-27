# Radio Fault Sim

A small Python toolkit for testing how controller code reacts to queued writes,
partial writes, stuck push-to-talk (PTT), crashes, and misleading feedback.

**Version 0.1.0 · Python 3.11+ · Apache-2.0 · No runtime dependencies**

The model runs in process with an explicit clock. It opens no radio, serial
device, socket, or audio stream. A modeled PTT line and reported feedback are
separate values, so a successful software command can be tested without treating
it as proof that a transmitter stopped.

## Run the examples

From a checkout with Python 3.11 or newer:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install .
.venv/bin/python -m radio_fault_sim --scenario stuck-ptt
.venv/bin/python -m radio_fault_sim --json
.venv/bin/python examples/stuck_transmitter.py
.venv/bin/python -m unittest discover -s tests -v
```

On Windows use `.venv\Scripts\python.exe` in place of `.venv/bin/python`.
Installation may download build tools. Once installed, examples and model calls
run offline. The package has not been published to PyPI.

## Use the model in a test

```python
from radio_fault_sim import Faults, SimTnc

sim = SimTnc(
    queue_delay_ms=100,
    ptt_duration_ms=300,
    faults=Faults(release_honored=False),
)
sim.attach("example-controller")
sim.write("example-controller", b"synthetic payload", mono_ms=0)

assert sim.snapshot().queued
assert not sim.snapshot().ptt_line
assert sim.advance(100).ptt_line
assert sim.advance(400).ptt_line
assert not sim.force_off()
```

The last assertion tests a failed release command. Inspect the separate
`ptt_line` and `feedback` fields when testing acknowledgment/state disagreement.
`write` queues new data; `advance` processes its due transitions. All untimed
commands operate at the most recently supplied simulated timestamp.

## Included scenarios

- Normal queue, key-up, and completion.
- A partial write that retains a one-byte prefix until canceled.
- Stuck PTT and an ignored release command.
- A crash that leaves the modeled line latched.
- Missing feedback and feedback that falsely says the line is off.
- A release acknowledgment that leaves the modeled line on.
- Conflicting queue ownership.
- One time step that crosses a whole transmission.

Run one with `--scenario NAME`; see `--help` for names. JSON output contains
synthetic samples and command outcomes, without packet contents.

## Scope

This is a controller fault model. It does not implement KISS framing, AX.25,
CSMA carrier sensing, modem audio, propagation, real-time scheduling, or RF
delivery. The queue delay and PTT duration are configured constants. The model
does not establish the behavior or safety of any physical TNC or radio.

See [model behavior](docs/MODEL.md), [scenario results](docs/SCENARIOS.md),
[validation](docs/VALIDATION.md), and [provenance](PROVENANCE.md).

## Project and license

Maintained by Mountain Brief Foundation. Copyright 2026 Mountain Brief LLC.
Released under the Apache License, Version 2.0. See [LICENSE](LICENSE),
[NOTICE](NOTICE), and [release status](RELEASE_STATUS.md).
