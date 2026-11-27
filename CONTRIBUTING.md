# Contributing

Keep the core deterministic, small, and free of hardware or network I/O.
Proposed changes should include a minimal synthetic scenario, expected states,
and a regression test. Avoid real callsigns, infrastructure addresses, payloads,
credentials, or logs from operational systems in test data.

Install the local package and run:

```sh
python -m unittest discover -s tests -v
python -m radio_fault_sim --json
```

Useful future work includes independently reviewed fault scenarios, tests of
controller integrations, and comparisons with real measurements that clearly
identify hardware and configuration. Keep hardware adapters separately scoped.
Do not present a simulated result as physical validation.

This private candidate is not yet open for public contributions. A public
contribution and licensing policy will accompany an approved release.
