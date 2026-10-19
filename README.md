# CSCI 4550 Mini Internet Project

A small virtual internet built in Python 3 using UDP sockets. Two hosts exchange messages through four routers, each running as its own process on one machine. After the common network works, we extend it with **Track B: reliable transfer** (stop-and-wait with ACKs, timeouts, retransmission and duplicate detection).

## Team

| Member | Area |
|---|---|
| Aida Bah | Packets & Hosts |
| Breona Saffouri | Routers & Configs |
| Sahand Darwish | Conditions, Logs & Evidence |

## Topology

```
              RB
             /  \
H1 —— RA          RD —— H2
             \  /
              RC
```

All links are bidirectional. H1 and H2 are never neighbors, so all traffic passes through the routers. The upper path goes through RB and the lower path through RC; the active path is chosen by the static forwarding tables.

### Devices

| Device | Virtual address | UDP endpoint |
|---|---|---|
| Host 1 | H1 | 127.0.0.1:50001 |
| Router A | RA | 127.0.0.1:50002 |
| Router B | RB | 127.0.0.1:50003 |
| Router C | RC | 127.0.0.1:50004 |
| Router D | RD | 127.0.0.1:50005 |
| Host 2 | H2 | 127.0.0.1:50006 |

Ports 50001–50006 avoid conflicts with port 5000, which macOS uses.

### Links

| Link | Role |
|---|---|
| H1 ↔ RA | edge |
| RA ↔ RB | upper path |
| RB ↔ RD | upper path |
| RA ↔ RC | lower path |
| RC ↔ RD | lower path |
| RD ↔ H2 | edge |

## Requirements

- Python 3
- Wireshark (for packet captures)

## Setup and launch

Use Python 3 and run every command from the project root, with each process in its own terminal.

| | Windows | macOS / Linux |
|---|---|---|
| Python command | `python` | `python3` |
| Path separator | `src\host.py` | `src/host.py` |

The examples below use macOS/Linux syntax.

### Configuration files

| File | Purpose |
|---|---|
| `config/topology.json` | Every device's host, port and neighbors |
| `config/forwardingUpper.json` | Static routes for H1 ↔ H2 via RB |
| `config/forwardingLower.json` | Static routes for H1 ↔ H2 via RC |
| `config/forwardingLoop.json` | RA and RB forward H2 traffic to each other, for the hop-limit test |

To switch paths, restart the routers with a different forwarding file. The topology file stays the same.

### Routers (in progress)

```
python3 src/router.py RA --forwarding config/forwardingUpper.json
```

The router name is required (`RA`, `RB`, `RC` or `RD`), as is `--forwarding`. `--config` defaults to `config/topology.json`. The router currently parses its arguments; packet forwarding is being added.

### Host-only check with a fake router

Start the fake router first, then the host:

```
python3 tests/fake_neighbor.py RA --mode echo
python3 src/host.py H1 --count 4 --interval 1 --timeout 2
```

The fake neighbor supports `echo`, `drop` and `silent` modes for probe tests. Use `--mode send --target H1` to send a packet to a host and check its responder behavior.

The host's `--count` defaults to `0`, which leaves it listening and responding without sending probes. H1 listens on port 50001 and sends to its neighbor RA on port 50002; H2 listens on port 50006 and sends to RD on port 50005.

### Tests

```
python3 -m unittest discover -s tests
```

## Wireshark

Capture on the loopback interface and filter to project ports:

```
udp.port >= 50001 && udp.port <= 50006
```