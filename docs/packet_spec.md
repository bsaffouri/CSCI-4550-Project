# Packet envelope specification

This document defines the common packet format used by hosts and routers. Packet
encoding and validation do not perform any network I/O.

## Fields

Every packet is a JSON object. The fields allowed depend on the message type:

| Field | Type | Meaning | Example |
|---|---|---|---|
| `src` | text | Device address of the sender | `"H1"` |
| `dst` | text | Device address of the intended recipient | `"H2"` |
| `hop_limit` | whole number, at least 0 | Remaining forwarding allowance | `8` |
| `type` | text | Message kind from the allowed list | `"PROBE"` |
| `msg_id` | whole number, at least 0 | Identifier used to match replies and logs | `17` |
| `payload` | text | Message contents | `"hello"` |
| `seq` | whole number, at least 0 | The message's position in the stop-and-wait sequence | `0` |
| `run_id` | text | Identifies one transfer run, so packets from an old run are not confused with a new one | `"r1"` |

The first six fields are required on every packet. `seq` and `run_id` are
required on `DATA` and `ACK` packets only, and are not permitted on `PROBE` or
`ECHO` packets.

Additional fields are not permitted. A whole number is an integer; booleans are
not integers for this specification.

## Message types

The supported message types are `PROBE`, `ECHO`, `DATA`, and `ACK`.

- `PROBE` asks the destination for a reply.
- `ECHO` replies to one `PROBE`, returning the same `msg_id` and `payload`.
- `DATA` carries one numbered message, identified by its `seq` and `run_id`.
- `ACK` confirms one `DATA` message. It copies that message's `seq` and
  `run_id`, with `src` and `dst` swapped.

## Encoding and size

The fields are serialized as a JSON object and encoded as UTF-8 bytes. The
encoded packet, including all JSON punctuation and field names, must be no
larger than 1,200 bytes.

## Invalid packets

A packet is invalid if it cannot be decoded as UTF-8 JSON, is not a JSON object,
has a missing or extra field, has a field with the wrong type, uses an unknown
message type, has a negative `hop_limit`, `msg_id`, or `seq`, is missing `seq`
or `run_id` on a `DATA` or `ACK` packet, has `seq` or `run_id` on a `PROBE` or
`ECHO` packet, or exceeds the size limit. Implementations report these errors
with the packet module's `PacketError`.

## Hop-limit rule

A router drops a packet that arrives with `hop_limit` less than or equal to 1.
Otherwise, it subtracts 1 from the hop limit before forwarding the packet.
Hosts choose a fresh hop limit for packets they originate or generate as replies.

## Reliable transfer

A transfer sends `DATA` messages numbered `seq = 0, 1, ..., count - 1`, all
sharing one `run_id`. The sender supports two modes so the two can be compared
under the same conditions.

### Parameters

| Parameter | Default | Meaning |
|---|---|---|
| `--count` | `10` | Number of `DATA` messages in the run |
| `--timeout` | `0.5` s | How long stop-and-wait waits for an `ACK` before resending |
| `--retries` | `5` | Resends allowed after the first send, so up to 6 sends per message |
| `--interval` | `0.01` s | Minimum time between new `DATA` sends in both modes (at most 100 messages per second) |
| `--observe` | `2.0` s | How long best-effort collects `ACK`s after its last send |
| `--run-id` | `"r1"` | Label shared by every packet in the run |

The interval applies only between new messages. Resends in stop-and-wait are
not delayed by it.

### Matching an ACK

An `ACK` counts for a `DATA` message only if all of these hold: its `type` is
`ACK`, its `dst` is the sending host, its `run_id` matches the run, and its
`seq` matches the message. Any other packet received while waiting is logged
as ignored and does not change the sender's state. Checking `seq` keeps a late
`ACK` for an earlier copy from being mistaken for the current one.

### Stop-and-wait sender states

| State | What happens | Next state |
|---|---|---|
| `SEND(seq)` | Wait `interval` (except before `seq = 0`), send `DATA` for `seq`, set `attempt = 0` | `WAIT(seq)` |
| `WAIT(seq)` | Wait up to `timeout` for a matching `ACK`. Each attempt gets a fresh deadline. | Matching `ACK` → `SEND(seq + 1)`, or `DONE` after the last message. Timeout → `RESEND(seq)` |
| `RESEND(seq)` | `attempt += 1`. If `attempt <= retries`, resend the same bytes and count a retransmission. | `WAIT(seq)`, or `FAILED` if `attempt > retries` |
| `DONE` | Print `delivered X/count, retransmissions=Y, elapsed=Zs` | Exit code `0` |
| `FAILED` | Print `FAILED: no ACK for seq=... after N retries`, then the summary. The remaining messages are not sent. | Exit code `1` |

Only one message is in flight at a time. Failure is bounded: the sender gives
up after `retries` resends of a single message rather than waiting forever.
Elapsed time runs from the first send to the last `ACK` (or to the failure).

### Best-effort sender states

| State | What happens | Next state |
|---|---|---|
| `SENDING` | Send `DATA` for every `seq` once, `interval` apart. No waiting, no resending. | `OBSERVING` |
| `OBSERVING` | For `observe` seconds, record the unique `seq` values of matching `ACK`s | `DONE` |
| `DONE` | Print `sent=N, acked=X/N, elapsed=Zs (observed for Ws)` | Exit code `0` |

Best-effort never fails. Elapsed time runs from the first send to the last new
`ACK` (or to the last send if no `ACK` arrived), so idle time in the
observation window is not counted. `acked` is a sender-side estimate: a lost
`ACK` makes it undercount, so the receiver's count of delivered messages is the
authoritative result.

### Receiver states

| State | What happens | Next state |
|---|---|---|
| `LISTEN` | Wait for packets addressed to this host. Ignore any packet whose `dst` is another host, and any packet that is not `DATA`. | On `DATA` → `HANDLE` |
| `HANDLE` | Send an `ACK` that copies the message's `seq` and `run_id`, with `src` and `dst` swapped. If `(run_id, seq)` has not been seen, deliver the message. If it has, count a duplicate and do not deliver it again. | `LISTEN` |

The receiver acknowledges every valid `DATA`, including duplicates. A duplicate
means the sender never got the earlier `ACK`, so the sender needs another one to
move on. At the end of a run the receiver reports the unique messages delivered,
whether the full sequence `0` to `count - 1` arrived, and the number of
duplicates seen.