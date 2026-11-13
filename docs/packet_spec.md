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

- `DATA` carries one numbered message, identified by its `seq` and `run_id`.
- `ACK` confirms one `DATA` message. It copies that message's `seq` and
  `run_id`, with `src` and `dst` swapped.
- `PROBE` asks the destination for a reply.
- `ECHO` replies to one `PROBE`, returning the same `msg_id` and `payload`.

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