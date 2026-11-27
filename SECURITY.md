# Security and issue reporting

The model accepts caller-supplied time, bytes, and configuration. It performs no
device, network, audio, or child-process I/O. Its default retained payload is
bounded to 4096 bytes, with one queued payload and no retained event history.
Caller-owned lists of snapshots and any future adapters need their own limits.

Report suspected security issues privately to stijn@mountainbrief.com. Include a
minimal synthetic reproduction and package version, without operational data
or secrets. No response-time commitment is implied by this candidate.

The examples are fault demonstrations. Their output does not establish radio
authorization, electrical interlocking, watchdog behavior, delivery, or safety
of a physical installation.
