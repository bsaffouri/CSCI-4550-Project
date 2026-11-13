"""Packet serialization and validation. This module intentionally does no I/O."""

import json


BASE_FIELDS = frozenset(
    {"src", "dst", "hop_limit", "type", "msg_id", "payload"}
)
SEQUENCED_FIELDS = BASE_FIELDS | {"seq", "run_id"}

FIELDS_BY_TYPE = {
    "PROBE": BASE_FIELDS,
    "ECHO": BASE_FIELDS,
    "DATA": SEQUENCED_FIELDS,
    "ACK": SEQUENCED_FIELDS,
}

ALLOWED_TYPES = frozenset(FIELDS_BY_TYPE)
MAX_PACKET_SIZE = 1200


class PacketError(ValueError):
    """Raised when a packet cannot be validated, encoded, or decoded."""


def validate_packet(packet):
    """Validate a packet dictionary and raise PacketError with the reason."""
    if not isinstance(packet, dict):
        raise PacketError("packet must be a JSON object")

    if "type" not in packet:
        raise PacketError("packet is missing required field(s): type")
    if not isinstance(packet["type"], str):
        raise PacketError("field 'type' must be text")
    if packet["type"] not in ALLOWED_TYPES:
        allowed = ", ".join(sorted(ALLOWED_TYPES))
        raise PacketError(
            f"unknown packet type {packet['type']!r}; allowed types: {allowed}"
        )

    expected = FIELDS_BY_TYPE[packet["type"]]

    missing = expected - packet.keys()
    if missing:
        fields = ", ".join(sorted(missing))
        raise PacketError(f"packet is missing required field(s): {fields}")

    extra = packet.keys() - expected
    if extra:
        fields = ", ".join(sorted(extra))
        raise PacketError(
            f"{packet['type']} packet has unknown field(s): {fields}"
        )

    for field in ("src", "dst", "payload"):
        if not isinstance(packet[field], str):
            raise PacketError(f"field '{field}' must be text")

    for field in ("hop_limit", "msg_id"):
        if type(packet[field]) is not int:
            raise PacketError(f"field '{field}' must be a whole number")
        if packet[field] < 0:
            raise PacketError(f"field '{field}' must be at least 0")

    if expected is SEQUENCED_FIELDS:
        if type(packet["seq"]) is not int:
            raise PacketError("field 'seq' must be a whole number")
        if packet["seq"] < 0:
            raise PacketError("field 'seq' must be at least 0")
        if not isinstance(packet["run_id"], str):
            raise PacketError("field 'run_id' must be text")


def encode_packet(packet):
    """Validate and encode a packet dictionary as UTF-8 JSON bytes."""
    validate_packet(packet)
    try:
        encoded = json.dumps(packet, separators=(",", ":")).encode("utf-8")
    except (TypeError, ValueError, UnicodeEncodeError, RecursionError) as exc:
        raise PacketError(f"packet cannot be encoded as JSON: {exc}") from exc

    if len(encoded) > MAX_PACKET_SIZE:
        raise PacketError(
            f"encoded packet is {len(encoded)} bytes; maximum is {MAX_PACKET_SIZE}"
        )
    return encoded


def decode_packet(data):
    """Decode UTF-8 JSON bytes, validate the packet, and return its dictionary."""
    if not isinstance(data, bytes):
        raise PacketError("packet data must be bytes")
    if len(data) > MAX_PACKET_SIZE:
        raise PacketError(
            f"encoded packet is {len(data)} bytes; maximum is {MAX_PACKET_SIZE}"
        )
    if not data:
        raise PacketError("packet data is empty")

    try:
        text = data.decode("utf-8")
        packet = json.loads(text)
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
        raise PacketError(f"packet is not valid UTF-8 JSON: {exc}") from exc

    validate_packet(packet)
    return packet
