"""All values are synthetic; the example controls no radio."""

from radio_fault_sim import Faults, SimTnc

sim = SimTnc(queue_delay_ms=100, ptt_duration_ms=300, faults=Faults(release_honored=False))
sim.attach("example-controller")
sim.write("example-controller", b"synthetic payload", mono_ms=0)
assert sim.snapshot().ptt_line is False
assert sim.advance(100).ptt_line is True
assert sim.advance(400).ptt_line is True
assert sim.force_off() is False
print("Modeled PTT remains on after the release command.")
