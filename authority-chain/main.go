package main

import (
	"bytes"
	"crypto/hmac"
	"crypto/sha256"
	"encoding/base64"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"log"
	"net"
	"net/http"
	"os"
	"strings"
	"sync"
	"time"

	"github.com/gorilla/websocket"
	"google.golang.org/grpc"
)

type Event struct {
	ID           string  `json:"id"`
	OrgID        string  `json:"org_id,omitempty"`
	Submitter    string  `json:"submitter,omitempty"`
	EnvelopeID   string  `json:"envelope_id,omitempty"`
	OriginPeerID string  `json:"origin_peer_id,omitempty"`
	DeviceID     string  `json:"device_id"`
	EventType    string  `json:"event_type"`
	Confidence   float64 `json:"confidence"`
	Location     string  `json:"location,omitempty"`
	FrameHash    string  `json:"frame_hash,omitempty"`
	Signature    string  `json:"signature,omitempty"`
	Status       string  `json:"status"`
	Timestamp    int64   `json:"timestamp"`
}

type requestContext struct {
	Internal bool
	OrgID    string
}

type nestedEvent struct {
	DeviceID   string  `json:"device_id"`
	EventType  string  `json:"event_type"`
	Confidence float64 `json:"confidence"`
	Location   string  `json:"location,omitempty"`
	FrameHash  string  `json:"frame_hash,omitempty"`
	Signature  string  `json:"signature,omitempty"`
}

type nestedSubmission struct {
	Submitter    string      `json:"submitter"`
	EnvelopeID   string      `json:"envelope_id"`
	OriginPeerID string      `json:"origin_peer_id"`
	APIKey       string      `json:"api_key"`
	Event        nestedEvent `json:"event"`
}

type simpleSubmission struct {
	Creator      string  `json:"creator"`
	APIKey       string  `json:"api_key"`
	DeviceID     string  `json:"device_id"`
	EventType    string  `json:"event_type"`
	Confidence   float64 `json:"confidence"`
	ConfidenceF  float64 `json:"confidence_f"`
	FrameHash    string  `json:"frame_hash,omitempty"`
	Signature    string  `json:"signature,omitempty"`
	EnvelopeID   string  `json:"envelope_id,omitempty"`
	OriginPeerID string  `json:"origin_peer_id,omitempty"`
	Location     string  `json:"location,omitempty"`
}

var (
	events      = make(map[string]Event)
	eventsLock  sync.RWMutex
	wsUpgrader  = websocket.Upgrader{CheckOrigin: func(r *http.Request) bool { return true }}
	wsClients   = make(map[*websocket.Conn]string)
	wsClientsMu sync.Mutex

	jwtSecret      = envOrDefault("JWT_SECRET", "CHANGE_ME_generate_with_openssl_rand_hex_32")
	internalAPIKey = os.Getenv("INTERNAL_API_KEY")
	authServiceURL  = envOrDefault("AUTH_SERVICE_URL", "http://auth-service:8700")
)

func main() {
	go startGRPCServer()
	startHTTPServer()
}

func envOrDefault(key, fallback string) string {
	value := strings.TrimSpace(os.Getenv(key))
	if value == "" {
		return fallback
	}
	return value
}

func startGRPCServer() {
	lis, err := net.Listen("tcp", ":9090")
	if err != nil {
		log.Fatalf("failed to listen: %v", err)
	}
	s := grpc.NewServer()
	log.Println("gRPC server listening on :9090")
	if err := s.Serve(lis); err != nil {
		log.Fatalf("failed to serve: %v", err)
	}
}

func startHTTPServer() {
	mux := http.NewServeMux()
	mux.HandleFunc("/health", healthHandler)
	mux.HandleFunc("/galaxy/v1/events", eventsHandler)
	mux.HandleFunc("/cosmos/tx/v1beta1/txs", cosmosTxsHandler)
	mux.HandleFunc("/websocket", wsHandler)
	mux.HandleFunc("/ws", wsHandler)

	log.Println("HTTP server listening on :1317")
	log.Fatal(http.ListenAndServe(":1317", mux))
}

func healthHandler(w http.ResponseWriter, _ *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]string{"status": "ok"})
}

func requestContextFromHTTP(r *http.Request) (requestContext, error) {
	if key := strings.TrimSpace(r.Header.Get("X-Internal-Auth")); key != "" {
		if internalAPIKey != "" && key == internalAPIKey {
			return requestContext{Internal: true, OrgID: "internal"}, nil
		}
		return requestContext{}, errors.New("invalid internal auth")
	}

	authHeader := strings.TrimSpace(r.Header.Get("Authorization"))
	if !strings.HasPrefix(authHeader, "Bearer ") {
		return requestContext{}, errors.New("authorization required")
	}

	return requestContextFromToken(strings.TrimSpace(strings.TrimPrefix(authHeader, "Bearer ")))
}

func requestContextFromWS(r *http.Request) (requestContext, error) {
	token := strings.TrimSpace(r.URL.Query().Get("token"))
	if token == "" {
		return requestContext{}, errors.New("authorization required")
	}
	return requestContextFromToken(token)
}

func requestContextFromToken(token string) (requestContext, error) {
	parts := strings.Split(token, ".")
	if len(parts) != 3 {
		return requestContext{}, errors.New("invalid token")
	}

	signingInput := parts[0] + "." + parts[1]
	providedSig, err := base64.RawURLEncoding.DecodeString(parts[2])
	if err != nil {
		return requestContext{}, errors.New("invalid token signature")
	}

	mac := hmac.New(sha256.New, []byte(jwtSecret))
	mac.Write([]byte(signingInput))
	expectedSig := mac.Sum(nil)
	if !hmac.Equal(providedSig, expectedSig) {
		return requestContext{}, errors.New("invalid token signature")
	}

	payloadBytes, err := base64.RawURLEncoding.DecodeString(parts[1])
	if err != nil {
		return requestContext{}, errors.New("invalid token payload")
	}

	var claims map[string]any
	if err := json.Unmarshal(payloadBytes, &claims); err != nil {
		return requestContext{}, errors.New("invalid token payload")
	}

	if tokenType := fmt.Sprint(claims["type"]); tokenType != "access" {
		return requestContext{}, errors.New("access token required")
	}

	if expRaw, ok := claims["exp"]; ok {
		exp, ok := toUnixSeconds(expRaw)
		if !ok {
			return requestContext{}, errors.New("invalid token expiry")
		}
		if time.Unix(exp, 0).Before(time.Now().UTC()) {
			return requestContext{}, errors.New("token expired")
		}
	}

	orgID := strings.TrimSpace(fmt.Sprint(claims["org_id"]))
	if orgID == "" {
		return requestContext{}, errors.New("org_id missing")
	}

	return requestContext{OrgID: orgID}, nil
}

func toUnixSeconds(value any) (int64, bool) {
	switch v := value.(type) {
	case float64:
		return int64(v), true
	case float32:
		return int64(v), true
	case int:
		return int64(v), true
	case int64:
		return v, true
	case json.Number:
		parsed, err := v.Int64()
		return parsed, err == nil
	default:
		return 0, false
	}
}

func resolveOrgID(apiKey string) string {
	apiKey = strings.TrimSpace(apiKey)
	if apiKey == "" {
		return "system"
	}

	reqBody, _ := json.Marshal(map[string]string{"api_key": apiKey})
	req, err := http.NewRequest(http.MethodPost, authServiceURL+"/internal/api-keys/resolve", bytes.NewReader(reqBody))
	if err != nil {
		log.Printf("auth resolve request build failed: %v", err)
		return "system"
	}
	req.Header.Set("Content-Type", "application/json")
	if internalAPIKey != "" {
		req.Header.Set("X-Internal-Auth", internalAPIKey)
	}

	client := &http.Client{Timeout: 2 * time.Second}
	resp, err := client.Do(req)
	if err != nil {
		log.Printf("auth resolve request failed: %v", err)
		return "system"
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(io.LimitReader(resp.Body, 256))
		log.Printf("auth resolve status=%d body=%s", resp.StatusCode, strings.TrimSpace(string(body)))
		return "system"
	}

	var parsed struct {
		OrgID string `json:"org_id"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&parsed); err != nil {
		return "system"
	}
	if parsed.OrgID == "" {
		return "system"
	}
	return parsed.OrgID
}

func parseSubmission(body []byte) (Event, string, error) {
	var raw map[string]json.RawMessage
	if err := json.Unmarshal(body, &raw); err != nil {
		return Event{}, "", err
	}

	if _, ok := raw["event"]; ok {
		var submitted nestedSubmission
		if err := json.Unmarshal(body, &submitted); err != nil {
			return Event{}, "", err
		}
		event := Event{
			Submitter:    submitted.Submitter,
			EnvelopeID:   submitted.EnvelopeID,
			OriginPeerID: submitted.OriginPeerID,
			DeviceID:     submitted.Event.DeviceID,
			EventType:    submitted.Event.EventType,
			Confidence:   submitted.Event.Confidence,
			Location:     submitted.Event.Location,
			FrameHash:    submitted.Event.FrameHash,
			Signature:    submitted.Event.Signature,
		}
		return event, strings.TrimSpace(submitted.APIKey), nil
	}

	var submitted simpleSubmission
	if err := json.Unmarshal(body, &submitted); err != nil {
		return Event{}, "", err
	}
	deviceID := strings.TrimSpace(submitted.DeviceID)
	if deviceID == "" {
		return Event{}, "", errors.New("device_id is required")
	}
	eventType := strings.TrimSpace(submitted.EventType)
	if eventType == "" {
		return Event{}, "", errors.New("event_type is required")
	}
	confidence := submitted.Confidence
	if confidence == 0 && submitted.ConfidenceF > 0 {
		confidence = submitted.ConfidenceF
	}
	if confidence <= 0 {
		return Event{}, "", errors.New("confidence is required")
	}

	event := Event{
		Submitter:    submitted.Creator,
		EnvelopeID:   submitted.EnvelopeID,
		OriginPeerID: submitted.OriginPeerID,
		DeviceID:     deviceID,
		EventType:    eventType,
		Confidence:   confidence,
		Location:     submitted.Location,
		FrameHash:    submitted.FrameHash,
		Signature:    submitted.Signature,
	}
	return event, strings.TrimSpace(submitted.APIKey), nil
}

func eventsHandler(w http.ResponseWriter, r *http.Request) {
	ctx, err := requestContextFromHTTP(r)
	if err != nil {
		http.Error(w, err.Error(), http.StatusUnauthorized)
		return
	}

	switch r.Method {
	case http.MethodGet:
		eventsLock.RLock()
		list := make([]Event, 0, len(events))
		for _, ev := range events {
			if ctx.Internal || ev.OrgID == ctx.OrgID {
				list = append(list, ev)
			}
		}
		eventsLock.RUnlock()
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]any{"events": list, "total": len(list)})
	case http.MethodPost:
		body, err := io.ReadAll(io.LimitReader(r.Body, 1<<20))
		if err != nil {
			http.Error(w, "failed to read body", http.StatusBadRequest)
			return
		}

		event, apiKey, err := parseSubmission(body)
		if err != nil {
			http.Error(w, err.Error(), http.StatusBadRequest)
			return
		}

		if ctx.Internal {
			event.OrgID = resolveOrgID(apiKey)
		} else {
			event.OrgID = ctx.OrgID
		}
		if event.OrgID == "" {
			http.Error(w, "org_id missing", http.StatusUnauthorized)
			return
		}

		if event.ID == "" {
			if event.EnvelopeID != "" {
				event.ID = event.EnvelopeID
			} else {
				event.ID = time.Now().UTC().Format(time.RFC3339Nano)
			}
		}
		event.Timestamp = time.Now().Unix()
		if event.Status == "" {
			event.Status = "pending"
		}

		eventsLock.Lock()
		events[event.ID] = event
		eventsLock.Unlock()

		broadcastEvent(event)

		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusCreated)
		json.NewEncoder(w).Encode(event)
	default:
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
	}
}

func cosmosTxsHandler(w http.ResponseWriter, r *http.Request) {
	ctx, err := requestContextFromHTTP(r)
	if err != nil {
		http.Error(w, err.Error(), http.StatusUnauthorized)
		return
	}

	eventsLock.RLock()
	defer eventsLock.RUnlock()

	rows := make([]Event, 0, len(events))
	for _, ev := range events {
		if ctx.Internal || ev.OrgID == ctx.OrgID {
			rows = append(rows, ev)
		}
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]any{"txs": rows})
}

func wsHandler(w http.ResponseWriter, r *http.Request) {
	ctx, err := requestContextFromWS(r)
	if err != nil {
		http.Error(w, err.Error(), http.StatusUnauthorized)
		return
	}

	conn, err := wsUpgrader.Upgrade(w, r, nil)
	if err != nil {
		log.Println("WebSocket upgrade error:", err)
		return
	}
	defer conn.Close()

	wsClientsMu.Lock()
	wsClients[conn] = ctx.OrgID
	wsClientsMu.Unlock()
	defer func() {
		wsClientsMu.Lock()
		delete(wsClients, conn)
		wsClientsMu.Unlock()
	}()

	for {
		if _, _, err := conn.ReadMessage(); err != nil {
			break
		}
	}
}

func broadcastEvent(ev Event) {
	payload := map[string]any{
		"jsonrpc": "2.0",
		"id":      "galaxy-sub",
		"result": map[string]any{
			"query": "tm.event='Tx' AND message.action='submit_event'",
			"data": map[string]any{
				"type": "tendermint/event/Tx",
				"value": map[string]any{
					"TxResult": map[string]any{
						"height": fmt.Sprintf("%d", ev.Timestamp),
						"result": map[string]any{
							"events": map[string][]string{
								"message.action":     {"submit_event"},
								"message.module":     {"galaxy"},
								"galaxy.device_id":   {ev.DeviceID},
								"galaxy.event_type":  {ev.EventType},
								"galaxy.status":      {ev.Status},
								"galaxy.envelope_id": {ev.EnvelopeID},
							},
						},
					},
				},
			},
		},
	}

	data, _ := json.Marshal(payload)
	wsClientsMu.Lock()
	defer wsClientsMu.Unlock()
	for conn, orgID := range wsClients {
		if orgID != ev.OrgID {
			continue
		}
		if err := conn.WriteMessage(websocket.TextMessage, data); err != nil {
			conn.Close()
			delete(wsClients, conn)
		}
	}
}
