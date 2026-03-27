#!/usr/bin/env python3
"""Phase V integration test: economy + webhook + compliance + prior flows."""

import random
import string
import sys
import time

import requests

AUTHORITY = "http://localhost:1317"
EDGE = "http://localhost:8100"
FL_AGGREGATOR = "http://localhost:8200"
PREDICTIVE = "http://localhost:8300"
WEBHOOK = "http://localhost:8500"
COMPLIANCE = "http://localhost:8400"


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


def register_planet(device_id: str, wallet: str):
    print_header("Register planet wallet for token rewards")
    res = requests.post(
        f"{AUTHORITY}/economy/v1/planet/register",
        json={"device_id": device_id, "wallet": wallet},
        timeout=8,
    )
    if res.status_code != 200:
        fail(f"planet register failed: {res.text}")
    print_ok(f"Planet {device_id} mapped to wallet {wallet}")


def device_balance(device_id: str) -> dict:
    res = requests.get(f"{AUTHORITY}/economy/v1/balance/by-device/{device_id}", timeout=8)
    if res.status_code != 200:
        fail(f"balance query failed: {res.text}")
    return res.json()


def register_webhook_subscription():
    print_header("Register tenant webhook subscription")
    target = "http://webhook-service:8500/debug/mock-receiver"
    res = requests.post(
        f"{WEBHOOK}/webhooks/register",
        json={"tenant_id": "tenant-a", "target_url": target, "enabled": True},
        timeout=8,
    )
    if res.status_code != 200:
        fail(f"webhook registration failed: {res.text}")
    print_ok("Webhook subscription registered")


def wait_for_webhook_delivery(timeout=40):
    print_header("Verify webhook delivery")
    deadline = time.time() + timeout
    while time.time() < deadline:
        res = requests.get(f"{WEBHOOK}/debug/received?limit=10", timeout=8)
        if res.status_code == 200:
            data = res.json()
            if data.get("count", 0) > 0:
                print_ok("Webhook delivery captured by debug receiver")
                return data
        time.sleep(2)
    fail("webhook delivery was not observed in time")


def verify_compliance_redaction():
    print_header("Verify compliance redaction and encryption")
    payload = {
        "tenant": "tenant-a",
        "tenant_region": "eu",
        "event": {
            "device_id": "planet-01",
            "event_type": "health_alert",
            "confidence": 0.95,
            "name": "Alice",
            "person_name": "Alice Example",
        },
    }
    res = requests.post(f"{COMPLIANCE}/transform", json=payload, timeout=8)
    if res.status_code != 200:
        fail(f"compliance transform failed: {res.text}")

    body = res.json()
    transformed = body.get("event", {})
    if transformed.get("name") == "Alice":
        fail("GDPR masking did not redact 'name'")
    if "payload_encrypted" not in transformed:
        fail("HIPAA encryption field missing")
    print_ok("Compliance engine redaction and encryption verified")


def run_fl_once():
    print_header("Verify federated learning endpoints")

    status_res = requests.get(f"{EDGE}/fl/status", timeout=8)
    if status_res.status_code != 200:
        fail(f"edge FL status failed: {status_res.text}")
    status = status_res.json()
    print_info(f"edge FL enabled={status.get('enabled')} model_version={status.get('model_version')}")

    latest_before_res = requests.get(f"{FL_AGGREGATOR}/fl/model/latest", timeout=8)
    if latest_before_res.status_code != 200:
        fail(f"FL aggregator latest model failed: {latest_before_res.text}")
    latest_before = latest_before_res.json()

    train_res = requests.post(f"{EDGE}/fl/train-once", timeout=12)
    if train_res.status_code != 200:
        fail(f"edge FL train-once failed: {train_res.text}")
    print_ok("edge submitted one FL update")

    latest_after_res = requests.get(f"{FL_AGGREGATOR}/fl/model/latest", timeout=8)
    if latest_after_res.status_code != 200:
        fail(f"FL aggregator latest model (after update) failed: {latest_after_res.text}")
    latest_after = latest_after_res.json()

    if latest_after.get("version", 0) < latest_before.get("version", 0):
        fail("FL model version regressed")
    print_ok(
        f"FL aggregator reachable model version={latest_after.get('version')} pending integration active"
    )


def run_predictive_once(min_predictions=1):
    print_header("Verify predictive analytics endpoints")

    run_res = requests.post(f"{PREDICTIVE}/predictions/run-once", timeout=30)
    if run_res.status_code != 200:
        fail(f"predictive run-once failed: {run_res.text}")
    run_data = run_res.json()
    print_info(f"predictive generated={run_data.get('generated')} model_ready={run_data.get('model_ready')}")

    latest_res = requests.get(f"{PREDICTIVE}/predictions/latest", timeout=8)
    if latest_res.status_code != 200:
        fail(f"predictive latest failed: {latest_res.text}")
    latest = latest_res.json()
    count = latest.get("count", 0)

    if count < min_predictions:
        fail(f"expected at least {min_predictions} prediction(s), got {count}")

    print_ok(f"predictive service produced {count} alert(s)")


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
    print(f"\n{Colors.BOLD}{Colors.HEADER}=== GALAXY PHASE V EXPANSION TEST ==={Colors.ENDC}")

    wait_for_health(f"{AUTHORITY}/health", "authority")
    wait_for_health(f"{EDGE}/health", "edge-planet")
    wait_for_health(f"{FL_AGGREGATOR}/health", "fl-aggregator")
    wait_for_health(f"{PREDICTIVE}/health", "predictive-service")
    wait_for_health(f"{WEBHOOK}/health", "webhook-service")
    wait_for_health(f"{COMPLIANCE}/health", "compliance-engine")

    submitter = random_submitter()
    device_id = "planet-01"
    wallet = "galaxy1planetreward"

    register_planet(device_id, wallet)
    register_webhook_subscription()
    before = device_balance(device_id)
    print_info(f"Initial balance={before.get('balance')} staked={before.get('staked')}")

    send_events_via_edge(submitter, device_id, count=8)
    data = wait_for_authority_events(min_total=8)
    summarize(data)

    run_fl_once()
    run_predictive_once(min_predictions=1)
    verify_compliance_redaction()
    wait_for_webhook_delivery()

    after = device_balance(device_id)
    print_info(f"Post-event balance={after.get('balance')} staked={after.get('staked')}")
    if int(after.get("balance", 0)) <= int(before.get("balance", 0)):
        fail("token reward was not credited after verified events")
    print_ok("Token rewards credited to registered planet wallet")

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

    print_ok("Phase V economy + webhook + compliance flow verified")
    print_warn("Optional: open dashboard to inspect token balance and staking panel.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        fail("interrupted")
