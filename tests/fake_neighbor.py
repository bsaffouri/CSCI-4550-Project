"""Small UDP stand-in for a router, for local host testing only."""

import argparse
import json
import socket
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from packet import PacketError, decode_packet, encode_packet


DEFAULT_CONFIG = Path(__file__).resolve().parent.parent / "config" / "topology.json"
DEFAULT_HOP_LIMIT = 8


def endpoint_for(config_path, device):
    try:
        with config_path.open(encoding="utf-8") as config_file:
            topology = json.load(config_file)
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot load topology config {config_path}: {exc}") from exc
    devices = topology.get("devices") if isinstance(topology, dict) else None
    if not isinstance(devices, dict) or device not in devices:
        raise ValueError(f"device {device!r} is not present in topology")
    entry = devices[device]
    if not isinstance(entry, dict) or not isinstance(entry.get("host"), str):
        raise ValueError(f"topology entry for {device} needs a text host and port")
    port = entry.get("port")
    if type(port) is not int or not 1 <= port <= 65535:
        raise ValueError(f"topology port for {device} must be between 1 and 65535")
    return entry["host"], port


def run(args):
    listen_endpoint = endpoint_for(args.config, args.device)

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.bind(listen_endpoint)
        sock.settimeout(0.2)
        print(
            f"fake neighbor {args.device} listening on "
            f"{listen_endpoint[0]}:{listen_endpoint[1]}"
        )

        if args.mode == "send":
            target = endpoint_for(args.config, args.target)
            if args.packet == "garbage":
                data = b"not json"
            else:
                message = {
                    "src": args.device,
                    "dst": args.destination,
                    "hop_limit": DEFAULT_HOP_LIMIT,
                    "type": args.message_type,
                    "msg_id": args.msg_id,
                    "payload": args.payload,
                }
                data = encode_packet(message)
            sock.sendto(data, target)
            print(f"sent {args.packet} packet to {args.target} at {target}")
            deadline = time.monotonic() + args.wait
            while time.monotonic() < deadline:
                try:
                    response, sender = sock.recvfrom(65535)
                except socket.timeout:
                    continue
                try:
                    packet = decode_packet(response)
                    print(f"received from {sender}: {packet}")
                except PacketError as exc:
                    print(f"received invalid packet from {sender}: {exc}")
            return

        probe_number = 0
        while True:
            try:
                data, sender = sock.recvfrom(65535)
            except socket.timeout:
                continue

            try:
                packet = decode_packet(data)
            except PacketError as exc:
                print(f"received invalid packet from {sender}: {exc}")
                continue

            print(f"received from {sender}: {packet}")
            if args.mode == "silent" or packet["type"] != "PROBE":
                continue

            probe_number += 1
            if args.mode == "drop" and probe_number == args.drop_number:
                print(f"dropped probe number {probe_number}")
                continue

            echo = {
                "src": args.device,
                "dst": packet["src"],
                "hop_limit": DEFAULT_HOP_LIMIT,
                "type": "ECHO",
                "msg_id": packet["msg_id"],
                "payload": packet["payload"],
            }
            response = encode_packet(echo)
            sock.sendto(response, sender)
            print(f"sent to {sender}: {echo}")


def main():
    parser = argparse.ArgumentParser(
        description="Pretend to be a neighboring router for host tests."
    )
    parser.add_argument("device", choices=("RA", "RD"), help="router identity to emulate")
    parser.add_argument(
        "--mode", choices=("echo", "drop", "silent", "send"), default="echo"
    )
    parser.add_argument(
        "--drop-number", type=int, default=1, help="probe number to drop in drop mode"
    )
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)

    send = parser.add_argument_group("send mode")
    send.add_argument("--target", choices=("H1", "H2"), default="H1")
    send.add_argument("--packet", choices=("valid", "garbage"), default="valid")
    send.add_argument(
        "--destination", default="H1", help="packet dst (use another host to test ignore)"
    )
    send.add_argument("--message-type", choices=("PROBE", "ECHO"), default="PROBE")
    send.add_argument("--msg-id", type=int, default=1)
    send.add_argument("--payload", default="fake neighbor test")
    send.add_argument(
        "--wait",
        type=float,
        default=2.0,
        help="seconds to wait for a response in send mode",
    )
    args = parser.parse_args()

    if args.drop_number < 1:
        parser.error("--drop-number must be at least 1")
    if args.msg_id < 0:
        parser.error("--msg-id must be at least 0")
    if args.wait < 0:
        parser.error("--wait must be at least 0")
    if args.mode == "send" and args.device not in ("RA", "RD"):
        parser.error("send mode requires a router identity")

    try:
        run(args)
    except (ValueError, PacketError) as exc:
        parser.error(str(exc))
    except OSError as exc:
        parser.error(f"fake neighbor socket error: {exc}")


if __name__ == "__main__":
    main()
