# Scenario results

Run `python -m radio_fault_sim --json` for all nine synthetic scenarios.
The default examples use a 100 ms queue delay and a 300 ms PTT duration.

| CLI name | Observation to check |
| --- | --- |
| normal | Queued at 0 ms; line on at 100 ms; queue and line clear at 400 ms |
| partial-write | One byte is retained after the short-write exception; acknowledged cancellation clears it |
| stuck-ptt | Line remains on at 400 ms; release command returns false |
| crash-latched | Controller is down and modeled line remains on after the nominal completion time |
| feedback-lost | Line can be on while feedback is `lost` |
| feedback-false-off | Line can be on while feedback is `off` |
| release-lies | Release returns true while the line remains on immediately after the command |
| ownership-conflict | Second controller is refused and the first payload remains |
| coarse-clock | A single step to 2000 ms leaves the normal queue and line clear |

Each result contains `outcomes` and a bounded list of sampled states. The CLI
uses a finite built-in set of scenarios and collects no external observations.
These samples demonstrate the model's specified behavior; they do not measure
real hardware or prove that a controller handles these failures correctly.
