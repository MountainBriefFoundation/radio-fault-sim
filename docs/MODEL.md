# Model behavior

## Time and state

The clock starts at zero. Timestamps and configuration durations are
nonnegative integer milliseconds; PTT duration and payload limit must be
positive. Boolean, floating-point, and backwards timestamps are rejected.

There is one attached controller and one queue. Controller names are bounded to
128 characters. The default payload limit is 4096 bytes and can be configured.
Payloads must be nonempty bytes or bytearrays; mutable input is copied. The
model retains no event history. Snapshots are immutable values owned by callers.

`write(owner, payload, mono_ms)` first settles an existing transmission at that
timestamp, then queues new data. Call `advance(mono_ms)` to process the new
frame. Repeating the same timestamp is allowed. Thus a zero-delay write can be
canceled before its first `advance` call. Actions at the same time follow the
order in which the caller invokes them.

On an ordinary advance, key-up is due at the queued time plus `queue_delay_ms`.
Completion is due after `ptt_duration_ms` more. A single large step processes
both transitions if both are due. It returns the final state, without inventing
observations of a transient pulse. Code needing edge observations must choose
appropriate sampling times. This is a single-threaded model.

`writes_accepted` counts complete payload writes accepted by this model. It does
not count validated protocol frames, transmissions, acknowledgments, or delivery.

## Fault configuration

Create a frozen `Faults` object at construction or replace it with `set_faults`.
Changing faults does not advance time; it changes reported feedback immediately.
Due physical-state transitions are processed by the next timed operation.

| Fault | Modeled result |
| --- | --- |
| Write DOWN or FAILED | Connection error, with no new queued payload |
| Write OCCUPIED | Queue-full error, with no new queued payload |
| Write PARTIAL | One byte of a multi-byte payload is retained; `PartialWriteError` reports the count |
| Cancel not honored | A queued payload remains and may subsequently key |
| Release not honored | Automatic completion and explicit release leave the line on |
| Release lies | Explicit release returns true while retaining queue and line state; ordinary timed completion still applies |
| Feedback UNAVAILABLE | Feedback is `lost`, independently of the line |
| Feedback FALSE_OFF | Feedback is `off`, independently of the line |
| Feedback FALSE_ON | Feedback is `on`, independently of the line |

A PARTIAL fault requires at least two input bytes. For a zero-byte acceptance
failure use FAILED instead. Partial queued bytes can key if they are not canceled;
this models uncertainty after a short write, without parsing a KISS frame.

In FOLLOW mode, feedback turns on `feedback_delay_ms` after modeled key-up.
It turns off immediately when the modeled line clears. A pulse shorter than
the feedback delay can finish without feedback ever being sampled on. This
asymmetric delay is an explicit simplification.

## Commands and crashes

`cancel(owner)` succeeds only for the attached owner, an unkeyed queue, a live
controller, and a configuration that honors cancellation. It clears queued data.
`force_off()` returns a modeled command acknowledgment. An honored release
clears queue and line; a lying acknowledgment leaves them unchanged.

`crash()` freezes queue and line state and marks the controller down. No later
write, cancellation, release, or automatic completion succeeds. A queued frame
does not newly key after a crash, and an already keyed line remains on. This is
one chosen controller failure model, not a universal claim about TNCs.

## Deliberate exclusions

There is no device adapter, TCP service, KISS/AX.25 codec, audio modem, RF channel,
slot scheduler, interlock, watchdog, key management, or transmit authorization.
Use the model alongside the controller under test; any future hardware adapter
requires its own design and evidence.
