#!/usr/bin/env python3
import requests
import time

r = requests.post(
    'http://localhost:8700/auth/register',
    json={'email': f'test-{int(time.time())}@test.com', 'password': 'Test1234!', 'org_name': 'Test'},
    timeout=5
)
print(f"Status: {r.status_code}")
print(f"Response: {r.json()}")
