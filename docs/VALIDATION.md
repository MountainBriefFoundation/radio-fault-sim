# Validation

Local checks on November 26, 2026 used the standalone candidate without any MB
application imports, credentials, infrastructure, or hardware.

| Environment | Test result |
| --- | --- |
| Linux x86-64, CPython 3.12.14 | 42 tests passed |
| Linux x86-64, CPython 3.13.5 | 42 tests passed |
| macOS arm64, CPython 3.11.15 | 42 tests passed; all nine CLI scenarios ran |
| macOS arm64, CPython 3.12.13 | 42 tests passed; all nine CLI scenarios ran |
| macOS arm64, CPython 3.13.13 | 42 tests passed; all nine CLI scenarios ran |
| macOS arm64, CPython 3.14.6 | 42 tests passed; all nine CLI scenarios ran |

A wheel was built with setuptools 84.2.1 and wheel 0.48.0. It installed without
dependency downloads into a clean Linux virtual environment. From a directory
outside the source tree, the installed package passed all 42 tests, its console
entry point emitted all nine scenarios, and the standalone example passed.
The imported module came from that environment's site-packages. Package
metadata declared no runtime dependencies and `pip check` found no broken
requirements. Build tools and package installation are separate from model I/O.

The regression suite includes boundary timing, coarse versus fine sampling,
partial-write retention, payload limits and copying, ownership conflicts,
cancellation, crashes, stuck PTT, and feedback/line disagreement. Scenario calls
also pass with file opening, sockets, child processes, and real-time sleeping
guarded against use.

The reviewed candidate passed all six Linux, macOS, and Windows jobs with
Python 3.11 and 3.14 in [GitHub CI run 45928199179](https://github.com/MountainBriefFoundation/radio-fault-sim/actions/runs/45928199179).
The table above records the separate local checks. The release changes license
and documentation files and package metadata; its runtime model and tests are
unchanged from that candidate. The workflow repeats tests and examples for new
commits.

No tests opened a radio, hardware interface, live TNC connection, or external
service. Passing tests establish the documented toy model and packaging
behavior. They do not establish interoperability, hardware timing, RF delivery,
physical interlocking, or safety of a real installation.
