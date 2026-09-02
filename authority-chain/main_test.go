package main

import (
	"crypto/hmac"
	"crypto/sha256"
	"encoding/base64"
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"
)

func signedToken(t *testing.T, claims map[string]any) string {
	t.Helper()
	header, err := json.Marshal(map[string]string{"alg": "HS256", "typ": "JWT"})
	if err != nil {
		t.Fatal(err)
	}
	payload, err := json.Marshal(claims)
	if err != nil {
		t.Fatal(err)
	}
	head := base64.RawURLEncoding.EncodeToString(header)
	body := base64.RawURLEncoding.EncodeToString(payload)
	input := head + "." + body
	mac := hmac.New(sha256.New, []byte(jwtSecret))
	_, _ = mac.Write([]byte(input))
	return input + "." + base64.RawURLEncoding.EncodeToString(mac.Sum(nil))
}

func TestRequestContextValidatesRegisteredClaims(t *testing.T) {
	jwtSecret = "test-secret-that-is-longer-than-thirty-two-characters"
	jwtIssuer = "galaxy-auth"
	jwtAudience = "galaxy-api"
	now := time.Now().Unix()
	token := signedToken(t, map[string]any{
		"sub": "user-1", "org_id": "org-1", "jti": "token-1",
		"type": "access", "iss": jwtIssuer, "aud": jwtAudience,
		"iat": now, "nbf": now - 1, "exp": now + 300,
	})
	ctx, err := requestContextFromToken(token)
	if err != nil {
		t.Fatalf("expected valid token: %v", err)
	}
	if ctx.OrgID != "org-1" {
		t.Fatalf("unexpected org: %s", ctx.OrgID)
	}

	bad := signedToken(t, map[string]any{
		"sub": "user-1", "org_id": "org-1", "jti": "token-2",
		"type": "access", "iss": "wrong", "aud": jwtAudience,
		"iat": now, "exp": now + 300,
	})
	if _, err := requestContextFromToken(bad); err == nil {
		t.Fatal("expected invalid issuer to be rejected")
	}
}

func TestLedgerDetectsTampering(t *testing.T) {
	tempDir := t.TempDir()
	authorityDataDir = tempDir
	eventLogPath = filepath.Join(tempDir, "events.jsonl")
	events = make(map[string]Event)
	eventOrder = nil
	lastRecordHash = ""

	event := Event{
		ID: "event-1", OrgID: "org-1", DeviceID: "device-1",
		EventType: "motion", Confidence: 0.9, Status: "pending",
		Timestamp: time.Now().Unix(),
	}
	if err := persistEventLocked(&event); err != nil {
		t.Fatal(err)
	}

	events = make(map[string]Event)
	eventOrder = nil
	lastRecordHash = ""
	if err := loadEvents(); err != nil {
		t.Fatalf("valid ledger should load: %v", err)
	}
	if len(eventOrder) != 1 {
		t.Fatalf("expected one event, got %d", len(eventOrder))
	}

	content, err := os.ReadFile(eventLogPath)
	if err != nil {
		t.Fatal(err)
	}
	tampered := strings.Replace(string(content), "motion", "intrusion", 1)
	if err := os.WriteFile(eventLogPath, []byte(tampered), 0o600); err != nil {
		t.Fatal(err)
	}
	events = make(map[string]Event)
	eventOrder = nil
	lastRecordHash = ""
	if err := loadEvents(); err == nil {
		t.Fatal("tampered ledger must be rejected")
	}
}

func TestParseSubmissionValidatesEvent(t *testing.T) {
	valid := []byte(`{"creator":"swarm","org_id":"org-1","device_id":"device-1","event_type":"fire","confidence_f":0.8}`)
	event, err := parseSubmission(valid)
	if err != nil {
		t.Fatalf("expected valid submission: %v", err)
	}
	if event.OrgID != "org-1" || event.Confidence != 0.8 {
		t.Fatalf("unexpected event: %#v", event)
	}

	invalid := []byte(`{"creator":"swarm","org_id":"org-1","device_id":"","event_type":"fire","confidence_f":0.8}`)
	if _, err := parseSubmission(invalid); err == nil {
		t.Fatal("missing device id must be rejected")
	}
}
