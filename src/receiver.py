"""Receiver for DATA/ACK transfer."""

import argparse
import socket
import sys
import time
from pathlib import Path

from host import DEFAULT_CONFIG, DEFAULT_HOP_LIMIT, load_host_config
from packet import PacketError, decode_packet, encode_packet


def run(args):
    own, neighbor, neighbor_id, peer = load_host_config(args.config, args.device)
    own_endpoint = (own["host"], own["port"])
    neighbor_endpoint = (neighbor["host"], neighbor["port"])

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.bind(own_endpoint)
        print(f"{args.device} receiver listening on {own_endpoint[0]}:{own_endpoint[1]}")

        seen = set()
        duplicates = 0

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

            if packet["dst"] != args.device or packet["type"] != "DATA":
                print(
                    f"ignored {packet['type']} from {sender} "
                    f"(dst={packet['dst']})"
                )
                continue

            ack = {
                "src": args.device,
                "dst": packet["src"],
                "hop_limit": DEFAULT_HOP_LIMIT,
                "type": "ACK",
                "msg_id": packet["msg_id"],
                "payload": "",
                "seq": packet["seq"],
                "run_id": packet["run_id"],
            }
            sock.sendto(encode_packet(ack), neighbor_endpoint)

            key = (packet["run_id"], packet["seq"])
            if key in seen:
                duplicates += 1
                print(f"duplicate DATA seq={packet['seq']} (duplicates={duplicates}), re-ACKed")
            else:
                seen.add(key)
                print(f"delivered DATA seq={packet['seq']} from {packet['src']}: {packet['payload']}")


def main():
    parser = argparse.ArgumentParser(
        description="Receive DATA messages and reply with ACKs."
    )
    parser.add_argument("device", choices=("H1", "H2"), help="which host is receiving")

    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument(
        "--linger", type=float, default=3.0, help="seconds to keep listening after the last DATA"
    )

    args = parser.parse_args()
    try:
        run(args)
    except (ValueError, PacketError) as exc:
        parser.error(str(exc))
    except OSError as exc:
        parser.error(f"receiver socket error: {exc}")


if __name__ == "__main__":
    main()