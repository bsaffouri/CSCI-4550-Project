"""Stop-and-wait and best-effort senders for DATA/ACK transfer."""

import argparse
import socket
import sys
import time
from pathlib import Path

from host import DEFAULT_CONFIG, DEFAULT_HOP_LIMIT, load_host_config
from packet import PacketError, decode_packet, encode_packet


RECEIVE_POLL_SECONDS = 0.05


def make_data(device, peer, seq, run_id):
    return {
        "src": device,
        "dst": peer,
        "hop_limit": DEFAULT_HOP_LIMIT,
        "type": "DATA",
        "msg_id": seq,
        "payload": f"message {seq}",
        "seq": seq,
        "run_id": run_id,
    }


def receive_packet(sock):
    """Return (packet, sender), or (None, None) if nothing valid arrived this poll."""
    try:
        data, sender = sock.recvfrom(65535)
    except socket.timeout:
        return None, None
    except ConnectionResetError as exc:
        print(f"neighbor reported an unreachable UDP destination: {exc}")
        return None, None

    try:
        return decode_packet(data), sender
    except PacketError as exc:
        print(f"invalid packet, dropped: {exc}")
        return None, None


def is_ack_for(packet, device, run_id):
    return (
        packet["type"] == "ACK"
        and packet["dst"] == device
        and packet["run_id"] == run_id
    )


def wait_for_ack(sock, device, run_id, seq, deadline):
    while time.monotonic() < deadline:
        packet, sender = receive_packet(sock)
        if packet is None:
            continue
        if is_ack_for(packet, device, run_id) and packet["seq"] == seq:
            return True
        print(
            f"ignored {packet['type']} from {sender} "
            f"(dst={packet['dst']}, run_id={packet.get('run_id')}, "
            f"seq={packet.get('seq')}); waiting for ACK seq={seq}"
        )
    return False


def run_stop_and_wait(sock, device, peer, neighbor_id, neighbor_endpoint,
                      count, timeout, retries, run_id, interval):
    delivered = 0
    retransmissions = 0
    failed = False
    start = time.monotonic()

    for seq in range(count):
        if seq > 0:
            time.sleep(interval)
        encoded = encode_packet(make_data(device, peer, seq, run_id))
        attempt = 0

        while True:
            sock.sendto(encoded, neighbor_endpoint)
            if attempt > 0:
                retransmissions += 1
                print(f"retransmit seq={seq} (attempt {attempt})")
            else:
                print(f"sent DATA seq={seq} to {peer} via {neighbor_id}")

            deadline = time.monotonic() + timeout
            if wait_for_ack(sock, device, run_id, seq, deadline):
                delivered += 1
                print(f"ACK seq={seq}")
                break

            print(f"timed out on seq={seq}")
            attempt += 1
            if attempt > retries:
                print(f"FAILED: no ACK for seq={seq} after {retries} retries")
                failed = True
                break

        if failed:
            break

    elapsed = time.monotonic() - start
    print(
        f"stop-and-wait: delivered {delivered}/{count}, "
        f"retransmissions={retransmissions}, elapsed={elapsed:.3f}s"
    )
    return not failed


def run_best_effort(sock, device, peer, neighbor_id, neighbor_endpoint,
                    count, run_id, interval, observe):
    start = time.monotonic()

    for seq in range(count):
        if seq > 0:
            time.sleep(interval)
        sock.sendto(encode_packet(make_data(device, peer, seq, run_id)), neighbor_endpoint)
        print(f"sent DATA seq={seq} to {peer} via {neighbor_id}")
    last_send_time = time.monotonic()

    acked = set()
    last_ack_time = None
    deadline = last_send_time + observe
    while time.monotonic() < deadline:
        packet, sender = receive_packet(sock)
        if packet is None:
            continue
        if is_ack_for(packet, device, run_id) and 0 <= packet["seq"] < count:
            if packet["seq"] not in acked:
                acked.add(packet["seq"])
                last_ack_time = time.monotonic()
                print(f"ACK seq={packet['seq']}")
        else:
            print(f"ignored {packet['type']} from {sender}")

    end = last_ack_time if last_ack_time is not None else last_send_time
    elapsed = end - start
    print(
        f"best-effort: sent={count}, acked={len(acked)}/{count}, "
        f"elapsed={elapsed:.3f}s (observed for {observe:.1f}s)"
    )
    return True


def run_sender(device, mode, count, timeout, retries, run_id, interval, observe,
               config_path):
    own, neighbor, neighbor_id, peer = load_host_config(config_path, device)
    own_endpoint = (own["host"], own["port"])
    neighbor_endpoint = (neighbor["host"], neighbor["port"])

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.bind(own_endpoint)
        sock.settimeout(RECEIVE_POLL_SECONDS)
        print(f"{device} sender ({mode}) listening on {own_endpoint[0]}:{own_endpoint[1]}")

        if mode == "best-effort":
            return run_best_effort(
                sock, device, peer, neighbor_id, neighbor_endpoint,
                count, run_id, interval, observe,
            )
        return run_stop_and_wait(
            sock, device, peer, neighbor_id, neighbor_endpoint,
            count, timeout, retries, run_id, interval,
        )


def main():
    parser = argparse.ArgumentParser(
        description="Send DATA messages using stop-and-wait or best-effort delivery."
    )
    parser.add_argument("device", choices=("H1", "H2"), help="which host is sending")
    parser.add_argument(
        "--mode",
        choices=("stop-and-wait", "best-effort"),
        default="stop-and-wait",
        help="delivery mode",
    )
    parser.add_argument("--count", type=int, default=10, help="number of messages")
    parser.add_argument(
        "--timeout", type=float, default=0.5, help="seconds to wait for an ACK (stop-and-wait)"
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=5,
        help="resends after the first send (5 means up to 6 sends per message)",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=0.01,
        help="minimum seconds between new DATA sends in both modes (0.01 = max 100 msg/s)",
    )
    parser.add_argument(
        "--observe",
        type=float,
        default=2.0,
        help="seconds best-effort waits for ACKs after the last send",
    )
    parser.add_argument("--run-id", default="r1", help="run label")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG, help="topology JSON path")
    args = parser.parse_args()

    if args.count < 0:
        parser.error("--count must be at least 0")
    if args.timeout <= 0:
        parser.error("--timeout must be greater than 0")
    if args.retries < 0:
        parser.error("--retries must be at least 0")
    if args.interval < 0:
        parser.error("--interval must be at least 0")
    if args.observe < 0:
        parser.error("--observe must be at least 0")

    try:
        ok = run_sender(
            args.device, args.mode, args.count, args.timeout, args.retries,
            args.run_id, args.interval, args.observe, args.config,
        )
    except ValueError as exc:
        parser.error(str(exc))
    except OSError as exc:
        parser.error(f"sender socket error: {exc}")

    if not ok:
        sys.exit(1)


if __name__ == "__main__":
    main()