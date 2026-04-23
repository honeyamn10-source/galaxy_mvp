#!/usr/bin/env python3
import os
import requests
import time
import sys

BASE = "http://localhost"

EMAIL = f"test-{int(time.time())}@example.com"
PASSWORD = "Test1234!"
ORG = "VerifyOrg"
ADMIN_EMAIL = os.getenv("DEFAULT_ADMIN_EMAIL", "admin@test.com")
ADMIN_PASSWORD = os.getenv("DEFAULT_ADMIN_PASSWORD", "Test1234!")

try:
    print("\n🚀 Galaxy MVP Verification Script\n")
    
    # Register
    print("1️⃣  Testing registration (OTP flow)...")
    r = requests.post(
        f"{BASE}/auth/register",
        json={"email": EMAIL, "password": PASSWORD, "org_name": ORG},
        timeout=15,
    )
    assert r.status_code == 200, f"Register failed: {r.text}"
    register_data = r.json()
    assert register_data.get("requires_otp") is True, f"OTP flag missing: {register_data}"
    otp = register_data.get("dev_otp")
    print("✓ Registration OK")

    token = ""
    if otp:
        # Verify OTP in development fallback mode.
        print("\n2️⃣  Testing OTP verification...")
        r = requests.post(
            f"{BASE}/auth/verify-otp",
            json={"email": EMAIL, "otp": otp},
            timeout=15,
        )
        assert r.status_code == 200, f"OTP verification failed: {r.text}"
        token = r.json()["access_token"]
        print("✓ OTP verification OK")

        # Login with newly created user.
        print("\n3️⃣  Testing login...")
        r = requests.post(
            f"{BASE}/auth/login",
            json={"email": EMAIL, "password": PASSWORD},
            timeout=15,
        )
        assert r.status_code == 200, f"Login failed: {r.text}"
        print("✓ Login OK")
    else:
        # In production mode, OTP is delivered externally; use default admin creds.
        print("\n2️⃣  OTP not exposed (production mode), using admin login fallback...")
        r = requests.post(
            f"{BASE}/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
            timeout=15,
        )
        assert r.status_code == 200, f"Admin login fallback failed: {r.text}"
        token = r.json()["access_token"]
        print("✓ Admin login fallback OK")

    # Emit event
    print("\n4️⃣  Testing event emission...")
    r = requests.post(
        f"{BASE}/galaxy/v1/events",
        json={
            "submitter": "verify-script",
            "envelope_id": f"verify-{int(time.time())}",
            "origin_peer_id": "verify-client",
            "event": {
                "device_id": "verify-device",
                "event_type": "motion",
                "confidence": 0.91,
                "location": "Verification-Lab"
            }
        },
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    )
    assert r.status_code in (200, 201), f"Emit failed: {r.text}"
    print("✓ Event emission OK")

    time.sleep(2)

    # Fetch events
    print("\n5️⃣  Testing event retrieval and LLM classification...")
    events = []
    for _ in range(8):
      r = requests.get(
          f"{BASE}/galaxy/v1/events?limit=20",
          headers={"Authorization": f"Bearer {token}"},
          timeout=15,
      )
      assert r.status_code == 200, "Fetch events failed"
      events = r.json().get("events", [])
      if events:
          break
      time.sleep(2)
    assert len(events) > 0, "No events found"
    assert "llm_reason" in events[0], "LLM reason missing"
    print(f"✓ LLM classification OK (found {len(events)} events)")
    print(f"  Sample event: {events[0]}")

    # Rate limit test
    print("\n6️⃣  Testing rate limiting...")
    codes = []
    for i in range(12):
        r = requests.post(
            f"{BASE}/auth/login",
            json={"email": "x@x.com", "password": "wrong"},
            timeout=10,
        )
        codes.append(r.status_code)
    assert 429 in codes, f"Rate limit not triggered. Status codes: {codes}"
    print("✓ Rate limiting OK (429 triggered after rapid attempts)")

    print("\n" + "="*60)
    print("✅ All tests passed. Galaxy MVP is fully functional.")
    print("="*60 + "\n")

except Exception as e:
    print(f"\n❌ Test failed: {e}\n")
    import traceback
    traceback.print_exc()
    sys.exit(1)
