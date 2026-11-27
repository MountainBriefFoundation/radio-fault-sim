# Provenance

Radio Fault Sim was adapted from a small in-process TNC/PTT simulation model
developed within Mountain Brief. The selected source file was independently
reviewed. No private repository history, scheduler, operational adapter,
configuration, credentials, live logs, or resident data was imported.

Original development was authored under Stijn Vanveerdeghem's account and
included Cursor-assisted coding. Extraction, API changes, tests, and documentation
included Codex-assisted coding and review. These facts do not establish that
every generated element is copyrightable or guarantee absence of third-party
rights. The selected source file has no third-party code notice or runtime
imports. Internal records retain its precise source snapshot and history.

The standalone version deliberately changes the original model:

- Removes modeled interlock/series-enable logic and RF-state helpers.
- Settles both key-up and completion when one step crosses the whole pulse.
- Rejects invalid and backwards time, blank owners, and unbounded payloads.
- Requires an attached owner and immutable copied payload storage.
- Represents fault configuration and snapshots with explicit types.
- Refuses cancellation through a crashed controller.
- Uses descriptive queue-delay, PTT-duration, and feedback-delay parameter names.
- Adds a one-byte partial-write precondition, false-on feedback, and standalone scenarios.

The package is a new API, not a drop-in replacement for an operational adapter.
Its runtime implementation uses the Python standard library only. Build tools
are separate dependencies. No source from another TNC simulator was copied for
this extraction. The ownership and proposed licensing record is described in
[release status](RELEASE_STATUS.md).
