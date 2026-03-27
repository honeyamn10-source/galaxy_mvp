#!/usr/bin/env python3
"""Phase III integration test: edge -> swarm -> authority chain."""

import random
import string
import sys
import time

import requests

AUTHORITY = "http://localhost:1317"
EDGE = "http://localhost:8100"


class Colors:
    HEADER = "\033[95m"
    OKCYAN = "\033[96m"
    OKGREEN = "\033[92m"
    WARNING = "\033[93m"
    FAIL = "\033[91m"
    ENDC = "\033[0m"
    BOLD = "\033[1m"


def print_header(msg):
    print(f"\n{Colors.HEADER}{Colors.BOLD}=== {msg} ==={Colors.ENDC}")


def print_ok(msg):
    print(f"{Colors.OKGREEN}✓ {msg}{Colors.ENDC}")


def print_info(msg):
    print(f"{Colors.OKCYAN}ℹ {msg}{Colors.ENDC}")


def print_warn(msg):
    print(f"{Colors.WARNING}! {msg}{Colors.ENDC}")


def fail(msg):
    print(f"{Colors.FAIL}✗ {msg}{Colors.ENDC}")
    sys.exit(1)


def wait_for_health(url, label, timeout=60):
    print_header(f"Health check: {label}")
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            res = requests.get(url, timeout=3)
            if res.status_code == 200:
                print_ok(f"{label} healthy")
                return
        except requests.RequestException:
            pass
        time.sleep(2)
    fail(f"{label} did not become healthy within {timeout}s")


def random_submitter() -> str:
    suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=10))
    return f"galaxy1{suffix}"


def send_events_via_edge(api_key, device_id, count):
    print_header("Publish events via edge simulator")
    payload = {
        "count": count,
        "api_key": api_key,
        "device_id": device_id,
        "location": "Region-1/Zone-Alpha",
        "interval_ms": 100,
    }
    res = requests.post(f"{EDGE}/emit-batch", json=payload, timeout=30)
    if res.status_code != 200:
        fail(f"edge publish failed: {res.text}")
    data = res.json()
    print_ok(f"Edge published {data['count']} events to swarm")


def wait_for_authority_events(min_total, timeout=30):
    print_header("Verify authority received swarm events")
    deadline = time.time() + timeout
    while time.time() < deadline:
        res = requests.get(f"{AUTHORITY}/galaxy/v1/events?limit=100", timeout=8)
        if res.status_code == 200:
            data = res.json()
            if data.get("total", 0) >= min_total:
                print_ok(f"Authority now has {data['total']} events")
                return data
        time.sleep(2)
    fail("events did not arrive from swarm to authority in time")


def summarize(data):
    print_header("Event summary")
    events = data.get("events", [])
    verified = sum(1 for e in events if e.get("status") == "verified")
    pending = len(events) - verified
    print_info(f"Displayed: {len(events)}")
    print_info(f"Total: {data['total']}")
    print_info(f"Verified: {verified}")
    print_info(f"Pending: {pending}")
    for event in events[:5]:
        print_info(
            f"tx={event['tx_hash']} type={event['event']['event_type']} conf={event['event']['confidence']:.2f} status={event['status']}"
        )


def main():
    print(f"\n{Colors.BOLD}{Colors.HEADER}=== GALAXY PHASE III AUTHORITY TEST ==={Colors.ENDC}")

    wait_for_health(f"{AUTHORITY}/health", "authority")
    wait_for_health(f"{EDGE}/health", "edge-planet")

    submitter = random_submitter()
    device_id = "planet-01"

    send_events_via_edge(submitter, device_id, count=8)
    data = wait_for_authority_events(min_total=8)
    summarize(data)

    cosmos_res = requests.get(
        f"{AUTHORITY}/cosmos/tx/v1beta1/txs",
        params={
            "limit": 5,
            "events": ["message.action='submit_event'", "message.module='galaxy'"],
        },
        timeout=8,
    )
    if cosmos_res.status_code == 200:
        print_ok("Cosmos transaction query endpoint reachable")

    print_ok("Phase III edge->swarm->authority flow verified")
    print_warn("Optional: open dashboard and switch data source to Cosmos.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        fail("interrupted")
