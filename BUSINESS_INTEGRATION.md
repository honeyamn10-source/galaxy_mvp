# Galaxy MVP Business Integration Guide (All 9 Sectors)

## 1. Introduction

Galaxy MVP helps organizations detect, verify, and respond to real-world events using a decentralized, API-first architecture.

What it delivers:
- Decentralized AI event detection from cameras, sensors, and existing software systems.
- Real-time event streaming and alerting through WebSocket and webhook channels.
- Multi-tenant operations with API keys per device/system.
- Rapid integration path for both modern and legacy infrastructure.

Business value:
- Faster incident detection and response.
- Lower integration risk by supporting both RTSP camera ingestion and direct HTTP event ingestion.
- Scalable rollout from pilot sites to enterprise-wide deployments.

Example dashboard URLs (replace with your final production URLs):
- https://galaxy-mvp.pages.dev
- https://galaxy-mvp.fly.dev

## 2. Common Integration Steps (Any Sector)

### Step 1: Register Your Organization

Use the dashboard or API to register your organization and admin user.

Dashboard access (example URLs):
- https://galaxy-mvp.pages.dev
- https://galaxy-mvp.fly.dev

API flow:
1. Register user and organization.
2. Verify OTP code sent by email.
3. Login and obtain access token.

### Step 2: Create Device API Keys

Create dedicated API keys for each camera gateway, sensor bridge, or external system.

Endpoint:
- POST /auth/api-keys

Use Authorization Bearer token from login/OTP verification.

### Step 3: Configure Alert Rules and Delivery Channels

Set event thresholds and destinations:
- Email to supervisors or on-call teams.
- Webhook to incident management/SOC/dispatch systems.
- SMS via your existing notification gateway (typically via webhook relay).

### Step 4: Send Events to Galaxy MVP

Send events from one of two paths:
- RTSP/IP camera path: RTSP stream into edge-planet, then emit events.
- Existing system path: direct HTTP POST events via /emit-batch or /galaxy/v1/events.

### Step 5: Subscribe to Real-Time Events

Use WebSocket to consume live event updates for control rooms, NOCs, and SIEM platforms.

### Step 6: Monitor and Operate in Dashboard

Use dashboard for:
- Real-time incident feed
- Event confidence and status
- Predictive alerts
- AI assistant queries for operational triage

Example dashboard URLs:
- https://galaxy-mvp.pages.dev
- https://galaxy-mvp.fly.dev

## 3. Sector-Specific Integration Playbooks

## 3.1 Smart City & Government

### Use Cases
- Illegal dumping detection near municipal bins.
- Intrusion detection around restricted public facilities.
- Fire detection in public parks or transport hubs.

### Realistic Example
Fire detection at a city electrical kiosk with automatic dispatch webhook to emergency command.

### Required Event Types
- fire
- intrusion
- motion
- smoke

### Hardware / Sensors
- City IP cameras (RTSP)
- Thermal cameras near critical infrastructure
- Acoustic/fire alarm relays
- Existing city command platform API

### Integration Method
- Primary: RTSP camera -> edge-planet -> Galaxy event pipeline.
- Alternate: municipal VMS sends direct HTTP POST events.

### How To Configure
1. Assign camera clusters by district using device_id naming (for example: city-d1-cam-22).
2. Configure RTSP_URL and EDGE_DEVICE_ID in edge-planet.
3. Create webhook rule for event_type=fire and intrusion.
4. Route webhook to emergency dispatch API.
5. Validate live feed in dashboard.

### Example Webhook Payload
{
  "tenant_id": "smart-city-ops",
  "source": "galaxy-authority",
  "event": {
    "device_id": "city-d1-cam-22",
    "event_type": "fire",
    "confidence": 0.93,
    "location": "Substation Block A",
    "status": "verified"
  },
  "delivered_at": "2026-04-02T21:00:00Z"
}

### Alert Actions
- Email to city control room lead.
- Webhook to police/fire dispatch API.
- Escalation webhook to city incident tracker if unresolved in 3 minutes.

### Pricing Recommendation
- Pilot: Free tier for 1-2 locations.
- Rollout: Paid tier based on events/month and district count.

### Dashboard Links
- https://galaxy-mvp.pages.dev
- https://galaxy-mvp.fly.dev

## 3.2 Industrial & Factories

### Use Cases
- Unauthorized entry into hazardous production zones.
- Early smoke/fire event detection near machinery.
- Machine anomaly events sent from PLC/SCADA bridge.

### Realistic Example
Intrusion detection at a chemical storage area triggering immediate plant security lock-down workflow.

### Required Event Types
- intrusion
- fire
- smoke
- machine_failure

### Hardware / Sensors
- IP CCTV cameras
- Thermal/smoke detectors
- PLC/SCADA event gateway
- Access control system API

### Integration Method
- Cameras via RTSP into edge-planet.
- Machine alarms via direct HTTP POST from SCADA middleware.

### How To Configure
1. Create separate API keys for each line/plant section.
2. Map machine alarms to event_type=machine_failure.
3. Configure fire/smoke alerts to EHS and plant manager channels.
4. Add webhook to CMMS/maintenance platform.

### Example Webhook Payload
{
  "tenant_id": "factory-alpha",
  "source": "galaxy-authority",
  "event": {
    "device_id": "line-4-gateway",
    "event_type": "machine_failure",
    "confidence": 0.88,
    "location": "Plant A - Line 4",
    "status": "verified"
  },
  "delivered_at": "2026-04-02T21:00:00Z"
}

### Alert Actions
- Email to EHS and operations manager.
- Webhook to maintenance ticketing/CMMS.
- Webhook to OT incident response runbook service.

### Pricing Recommendation
- Pilot: Free tier at one line.
- Production: Paid plan sized by event volume and number of plants.

### Dashboard Links
- https://galaxy-mvp.pages.dev
- https://galaxy-mvp.fly.dev

## 3.3 Real Estate & Buildings

### Use Cases
- Unauthorized access in parking and utility rooms.
- Elevator lobby crowding and after-hours intrusion.
- Fire/smoke incidents in common areas.

### Realistic Example
After-hours intrusion in a premium office tower basement parking triggers security patrol dispatch.

### Required Event Types
- intrusion
- motion
- fire
- smoke

### Hardware / Sensors
- Building CCTV and access-control logs
- Fire panel outputs
- Elevator and parking management APIs

### Integration Method
- RTSP feeds for cameras.
- Direct API POST for access control anomalies.

### How To Configure
1. Register each property as a logical device group.
2. Set alert routing by property and event type.
3. Connect webhook to building management or guard app.
4. Use dashboard filters per property/site.

### Example Webhook Payload
{
  "tenant_id": "real-estate-prime",
  "source": "galaxy-authority",
  "event": {
    "device_id": "tower-b2-cam-03",
    "event_type": "intrusion",
    "confidence": 0.91,
    "location": "Tower B - Basement 2",
    "status": "verified"
  },
  "delivered_at": "2026-04-02T21:00:00Z"
}

### Alert Actions
- Email to facility manager.
- Webhook to security guard dispatch system.
- Optional SMS escalation via webhook gateway.

### Pricing Recommendation
- Pilot: Free tier for one building.
- Portfolio rollout: Paid plan by number of buildings and monthly events.

### Dashboard Links
- https://galaxy-mvp.pages.dev
- https://galaxy-mvp.fly.dev

## 3.4 Oil, Gas & Energy

### Use Cases
- Perimeter intrusion at substations and depots.
- Fire and smoke detection at remote assets.
- Equipment anomaly events from telemetry systems.

### Realistic Example
Fire detection at a power substation with automatic alert to grid operations center.

### Required Event Types
- fire
- smoke
- intrusion
- machine_failure

### Hardware / Sensors
- Thermal + optical cameras
- Perimeter sensors
- SCADA telemetry alerts
- Remote station communication gateways

### Integration Method
- RTSP for visual monitoring assets.
- Direct API POST from SCADA/event broker for machine anomalies.

### How To Configure
1. Create API keys per asset cluster or station.
2. Configure RTSP ingestion for perimeter cameras.
3. Route critical events to control center and emergency response webhooks.
4. Add redundancy with multiple webhook endpoints.

### Example Webhook Payload
{
  "tenant_id": "energy-grid-west",
  "source": "galaxy-authority",
  "event": {
    "device_id": "substation-17-thermal",
    "event_type": "fire",
    "confidence": 0.95,
    "location": "Substation 17",
    "status": "verified"
  },
  "delivered_at": "2026-04-02T21:00:00Z"
}

### Alert Actions
- Email to grid duty engineer.
- Webhook to utility emergency response platform.
- Webhook to compliance/audit archive.

### Pricing Recommendation
- Pilot: Free tier for lab/testing substations.
- Enterprise: Paid plan with private deployment and SLA requirements.

### Dashboard Links
- https://galaxy-mvp.pages.dev
- https://galaxy-mvp.fly.dev

## 3.5 Logistics & Warehouses

### Use Cases
- Dock intrusion after shift close.
- Fire/smoke in storage aisles.
- Motion anomalies in high-value zones.

### Realistic Example
Intrusion at an outbound dock after midnight triggers alert to warehouse security and regional SOC.

### Required Event Types
- intrusion
- motion
- fire
- smoke

### Hardware / Sensors
- Warehouse IP cameras
- Smoke/fire sensors
- RFID/inventory exception feeds
- WMS integration endpoints

### Integration Method
- RTSP camera streams into edge-planet.
- WMS exceptions sent via direct API POST.

### How To Configure
1. Tag devices by site and zone.
2. Create alert rules by warehouse shift window.
3. Push webhook notifications to WMS/SOC.
4. Monitor high-volume events in dashboard.

### Example Webhook Payload
{
  "tenant_id": "logistics-north",
  "source": "galaxy-authority",
  "event": {
    "device_id": "wh-north-dock-7",
    "event_type": "intrusion",
    "confidence": 0.9,
    "location": "Dock 7",
    "status": "verified"
  },
  "delivered_at": "2026-04-02T21:00:00Z"
}

### Alert Actions
- Email to warehouse supervisor.
- Webhook to SOC and WMS incident module.
- Escalation webhook to third-party guard service.

### Pricing Recommendation
- Pilot: Free tier at one warehouse.
- Scale: Paid plan based on total camera count and monthly event throughput.

### Dashboard Links
- https://galaxy-mvp.pages.dev
- https://galaxy-mvp.fly.dev

## 3.6 Transportation & Highways

### Use Cases
- Wrong-way driving and road intrusion alerts.
- Tunnel smoke/fire detection.
- Traffic anomaly triggers integrated with ITS systems.

### Realistic Example
Smoke detection in a highway tunnel sends real-time webhook to traffic control and emergency services.

### Required Event Types
- smoke
- fire
- intrusion
- motion

### Hardware / Sensors
- Highway/tunnel cameras
- Environmental tunnel sensors
- ITS/traffic management feeds
- Variable message sign control APIs

### Integration Method
- RTSP from roadside cameras.
- Direct API from ITS anomaly engine.

### How To Configure
1. Group devices by corridor/segment.
2. Enable tunnel-specific smoke/fire alert rules.
3. Route webhook to traffic command center.
4. Optionally trigger signage workflows from external systems.

### Example Webhook Payload
{
  "tenant_id": "transport-east",
  "source": "galaxy-authority",
  "event": {
    "device_id": "tunnel-5-cam-2",
    "event_type": "smoke",
    "confidence": 0.94,
    "location": "Tunnel 5 - Southbound",
    "status": "verified"
  },
  "delivered_at": "2026-04-02T21:00:00Z"
}

### Alert Actions
- Email to highway operations lead.
- Webhook to ITS command API.
- Webhook to emergency dispatch integration.

### Pricing Recommendation
- Pilot: Free tier for a short corridor.
- Regional deployment: Paid plan by lane-miles and event rate.

### Dashboard Links
- https://galaxy-mvp.pages.dev
- https://galaxy-mvp.fly.dev

## 3.7 Healthcare (Advanced)

### Use Cases
- Patient fall detection in monitored zones.
- Restricted area intrusion in pharmacy/labs.
- Fire/smoke in equipment or storage areas.

### Realistic Example
Fall detection in a long-term care corridor triggers nurse station webhook and on-call escalation.

### Required Event Types
- fall_detection
- intrusion
- fire
- smoke

### Hardware / Sensors
- Corridor and room cameras (privacy policy compliant)
- Nurse call and bed sensor integration
- Access control and door sensors
- Hospital incident management APIs

### Integration Method
- RTSP feeds with edge-planet for visual detections.
- Existing nurse-call/RTLS systems post events directly by API.

### How To Configure
1. Define zones by unit/ward.
2. Route fall_detection events to nurse workflows.
3. Configure webhook to clinical operations platform.
4. Use role-based dashboard access for operations teams.

### Example Webhook Payload
{
  "tenant_id": "healthcare-advanced",
  "source": "galaxy-authority",
  "event": {
    "device_id": "ward-3-cam-11",
    "event_type": "fall_detection",
    "confidence": 0.89,
    "location": "Ward 3 Corridor",
    "status": "verified"
  },
  "delivered_at": "2026-04-02T21:00:00Z"
}

### Alert Actions
- Email to duty nurse manager.
- Webhook to nurse station workflow API.
- Escalation webhook to hospital incident command.

### Pricing Recommendation
- Pilot: Free tier for one ward or clinic.
- Hospital-wide: Paid plan with private cloud/on-prem requirements.

### Dashboard Links
- https://galaxy-mvp.pages.dev
- https://galaxy-mvp.fly.dev

## 3.8 Agriculture

### Use Cases
- Perimeter intrusion around farms and storage.
- Fire/smoke monitoring in barns and processing zones.
- Equipment anomaly events from irrigation/automation systems.

### Realistic Example
Smoke detected in grain storage triggers farmer alert and local emergency notification webhook.

### Required Event Types
- intrusion
- smoke
- fire
- machine_failure

### Hardware / Sensors
- Field/barn IP cameras
- Temperature and smoke sensors
- Irrigation controller telemetry
- Farm management software APIs

### Integration Method
- RTSP camera ingestion for visual events.
- Direct API POST from farm controllers/IoT gateways.

### How To Configure
1. Create API keys per farm site.
2. Map telemetry faults to machine_failure.
3. Configure webhook to farm management platform.
4. Add email alerts for owners and operators.

### Example Webhook Payload
{
  "tenant_id": "agri-south",
  "source": "galaxy-authority",
  "event": {
    "device_id": "grain-silo-cam-1",
    "event_type": "smoke",
    "confidence": 0.92,
    "location": "Silo 1",
    "status": "verified"
  },
  "delivered_at": "2026-04-02T21:00:00Z"
}

### Alert Actions
- Email to farm operations lead.
- Webhook to farm management system.
- SMS via webhook integration for remote areas.

### Pricing Recommendation
- Pilot: Free tier for one site.
- Multi-site agriculture groups: Paid tier by event volume and farm count.

### Dashboard Links
- https://galaxy-mvp.pages.dev
- https://galaxy-mvp.fly.dev

## 3.9 Retail Stores

### Use Cases
- After-hours intrusion detection.
- Fire/smoke alerts in stockrooms.
- High-risk motion patterns at entrances/exits.

### Realistic Example
After-hours intrusion at a flagship store triggers immediate webhook to security monitoring center.

### Required Event Types
- intrusion
- motion
- fire
- smoke

### Hardware / Sensors
- In-store and perimeter IP cameras
- Fire panel integration
- POS fraud/risk signal bridge (optional)
- Retail incident response tools

### Integration Method
- RTSP for camera-based detections.
- Direct HTTP POST from in-store systems for fraud/risk events.

### How To Configure
1. Register each branch as a device group.
2. Create branch-level API keys and alert channels.
3. Connect webhook to retailer SOC/ticketing platform.
4. Monitor all branches in dashboard and drill into site events.

### Example Webhook Payload
{
  "tenant_id": "retail-global",
  "source": "galaxy-authority",
  "event": {
    "device_id": "store-145-entry-cam",
    "event_type": "intrusion",
    "confidence": 0.9,
    "location": "Store 145 - Main Entrance",
    "status": "verified"
  },
  "delivered_at": "2026-04-02T21:00:00Z"
}

### Alert Actions
- Email to store manager and regional security.
- Webhook to SOC platform.
- Optional webhook to local guard provider API.

### Pricing Recommendation
- Pilot: Free tier for a few stores.
- Chain rollout: Paid plan by number of stores and monthly event volumes.

### Dashboard Links
- https://galaxy-mvp.pages.dev
- https://galaxy-mvp.fly.dev

## 4. How To Get Started Right Now

1. Register organization and user:

curl -X POST http://localhost/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"ops@example.com","password":"Test1234!","org_name":"Demo Org"}'

2. Verify OTP (replace value):

curl -X POST http://localhost/auth/verify-otp \
  -H "Content-Type: application/json" \
  -d '{"email":"ops@example.com","otp":"123456"}'

3. Login and get token:

curl -X POST http://localhost/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"ops@example.com","password":"Test1234!"}'

4. Create API key for a device:

curl -X POST http://localhost/auth/api-keys \
  -H "Authorization: Bearer <ACCESS_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"device_id":"site-1-cam-1","name":"Site Camera 1"}'

5. Send a test event:

curl -X POST http://localhost/emit-batch \
  -H "Content-Type: application/json" \
  -d '{"count":1,"api_key":"<DEVICE_API_KEY>","device_id":"site-1-cam-1","event_type":"intrusion","location":"Gate A"}'

6. Open dashboard and confirm event visibility:
- https://galaxy-mvp.pages.dev
- https://galaxy-mvp.fly.dev

## 5. Technical Appendices

### Appendix A: API Reference (Key Endpoints)

Authentication and tenancy:
- POST /auth/register
- POST /auth/verify-otp
- POST /auth/resend-otp
- POST /auth/login
- POST /auth/api-keys
- GET /auth/api-keys

Event ingestion and retrieval:
- POST /emit-batch
- POST /galaxy/v1/events
- GET /galaxy/v1/events

Real-time stream:
- WebSocket /websocket (authority service endpoint)

Webhook operations:
- POST /webhooks/register
- GET /webhooks/subscriptions
- GET /webhooks/dead-letters
- POST /debug/mock-receiver (testing)
- GET /debug/received (testing)

### Appendix B: Webhook Configuration Example

Register a webhook target:

curl -X POST http://localhost:8500/webhooks/register \
  -H "Content-Type: application/json" \
  -d '{"tenant_id":"demo-tenant","target_url":"https://webhook.site/your-id","enabled":true}'

### Appendix C: Sample Event Send Code

Python:

import requests

requests.post(
    "http://localhost/emit-batch",
    json={
        "count": 1,
        "api_key": "<DEVICE_API_KEY>",
        "device_id": "site-1-cam-1",
        "event_type": "fire",
        "location": "Zone A"
    },
    timeout=10,
)

curl:

curl -X POST http://localhost/emit-batch \
  -H "Content-Type: application/json" \
  -d '{"count":1,"api_key":"<DEVICE_API_KEY>","device_id":"site-1-cam-1","event_type":"fire","location":"Zone A"}'

### Appendix D: RTSP Camera Setup Guide

1. Configure camera stream URL:

export RTSP_URL=rtsp://username:password@camera-ip:554/stream
export EDGE_DEVICE_ID=camera-lobby-01

2. Start edge-planet:

docker compose up -d edge-planet

3. Validate camera ingestion:
- GET http://localhost:8100/camera/status

4. Optional: connect external inference engine:

export REAL_INFERENCE_URL=http://your-inference-service:9000/infer

### Appendix E: Deployment Model Note

For large-scale or regulated deployments, Galaxy team can provide:
- On-premise deployment
- Private cloud/VPC deployment
- Tenant-isolated environments with custom SLA and integration support

## 6. Contact & Support

To request a demo, integration workshop, or custom architecture review:
- Contact your Galaxy account team.
- Share your current camera/sensor inventory and target incident workflows.
- Request a pilot blueprint for one site, then scale to multi-site deployment.

Recommended onboarding path:
1. 2-week pilot at one location.
2. Validate alert quality and response workflows.
3. Expand by site clusters with standardized API/webhook templates.
