# API Integration Guide

This guide shows how an external service can integrate with Galaxy MVP.

## Base URLs

Gateway (default local):
- http://localhost

Direct services:
- Auth: http://localhost:8700
- Authority REST: http://localhost:1317
- WebSocket: ws://localhost:1317/websocket

## Authentication

Two auth patterns are available:
- Bearer JWT token for user and admin APIs.
- API key for edge/device event ingestion APIs.

## 1) Register/Login And Create Device API Key

### Register
POST /auth/register

Request:
{
  "email": "dev@example.com",
  "password": "Test1234!",
  "org_name": "Demo Org"
}

Response:
{
  "message": "OTP sent to email",
  "requires_otp": true
}

### Verify OTP
POST /auth/verify-otp

Request:
{
  "email": "dev@example.com",
  "otp": "123456"
}

Response includes access_token and refresh_token.

### Create API key
POST /auth/api-keys
Authorization: Bearer <access_token>

Request:
{
  "device_id": "camera-001",
  "name": "Lobby Camera"
}

Response:
{
  "api_key": "gal_xxx...",
  "device_id": "camera-001"
}

## 2) Send Events

### Endpoint
POST /emit-batch

Request:
{
  "count": 1,
  "api_key": "gal_xxx",
  "device_id": "camera-001",
  "event_type": "intrusion",
  "location": "Lobby"
}

### curl example
curl -X POST http://localhost/emit-batch \
  -H "Content-Type: application/json" \
  -d '{"count":1,"api_key":"gal_xxx","device_id":"camera-001","event_type":"intrusion","location":"Lobby"}'

### Python example
import requests

requests.post(
    "http://localhost/emit-batch",
    json={
        "count": 1,
        "api_key": "gal_xxx",
        "device_id": "camera-001",
        "event_type": "intrusion",
        "location": "Lobby"
    },
    timeout=10,
)

### JavaScript example
await fetch("http://localhost/emit-batch", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    count: 1,
    api_key: "gal_xxx",
    device_id: "camera-001",
    event_type: "intrusion",
    location: "Lobby"
  })
});

## 3) Fetch Events

GET /galaxy/v1/events?limit=50
Authorization: Bearer <access_token>

## 4) Subscribe To Real-Time Events

WebSocket endpoint:
- ws://localhost:1317/websocket

Subscription payload:
{
  "jsonrpc": "2.0",
  "method": "subscribe",
  "id": "external-client",
  "params": {
    "query": "tm.event='Tx' AND message.action='submit_event'"
  }
}

## 5) Webhook Alerts

Register webhook target:
POST /webhooks/register

Body:
{
  "tenant_id": "demo-tenant",
  "target_url": "https://your-service.example/webhook",
  "enabled": true
}

For local testing, use:
- https://webhook.site
- or built-in mock receiver: POST http://localhost:8500/debug/mock-receiver
- inspect deliveries: GET http://localhost:8500/debug/received

## Webhook Tester Example

curl -X POST http://localhost:8500/debug/mock-receiver \
  -H "Content-Type: application/json" \
  -d '{"source":"manual-test","event":{"device_id":"camera-001","event_type":"intrusion"}}'
