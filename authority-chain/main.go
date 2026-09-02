package main

import (
	"bufio"
	"bytes"
	"crypto/hmac"
	"crypto/sha256"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"sync"
	"time"

	"github.com/gorilla/websocket"
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
	Description  string  `json:"description,omitempty"`
	LLMReason    string  `json:"llm_reason,omitempty"`
	Location     string  `json:"location,omitempty"`
	FrameHash    string  `json:"frame_hash,omitempty"`
	Signature    string  `json:"signature,omitempty"`
	Status       string  `json:"status"`
	Timestamp    int64   `json:"timestamp"`
	PreviousHash string  `json:"previous_hash,omitempty"`
	RecordHash   string  `json:"record_hash"`
}

type requestContext struct {
	Internal bool
	OrgID    string
}

type nestedEvent struct {
	DeviceID    string  `json:"device_id"`
	EventType   string  `json:"event_type"`
	Confidence  float64 `json:"confidence"`
	Description string  `json:"description,omitempty"`
	Location    string  `json:"location,omitempty"`
	FrameHash   string  `json:"frame_hash,omitempty"`
	Signature   string  `json:"signature,omitempty"`
}

type nestedSubmission struct {
	Submitter    string      `json:"submitter"`
	EnvelopeID   string      `json:"envelope_id"`
	OriginPeerID string      `json:"origin_peer_id"`
	OrgID        string      `json:"org_id"`
	Event        nestedEvent `json:"event"`
}

type simpleSubmission struct {
	Creator      string  `json:"creator"`
	OrgID        string  `json:"org_id"`
	DeviceID     string  `json:"device_id"`
	EventType    string  `json:"event_type"`
	Confidence   float64 `json:"confidence"`
	ConfidenceF  float64 `json:"confidence_f"`
	Description  string  `json:"description,omitempty"`
	FrameHash    string  `json:"frame_hash,omitempty"`
	Signature    string  `json:"signature,omitempty"`
	EnvelopeID   string  `json:"envelope_id,omitempty"`
	OriginPeerID string  `json:"origin_peer_id,omitempty"`
	Location     string  `json:"location,omitempty"`
}

var (
	events      = make(map[string]Event)
	eventOrder  = make([]string, 0)
	eventsLock  sync.RWMutex
	lastRecordHash string
	wsUpgrader  = websocket.Upgrader{CheckOrigin: allowedWebSocketOrigin}
	wsClients   = make(map[*websocket.Conn]string)
	wsClientsMu sync.Mutex

	jwtSecret       = strings.TrimSpace(os.Getenv("JWT_SECRET"))
	jwtIssuer       = envOrDefault("JWT_ISSUER", "galaxy-auth")
	jwtAudience     = envOrDefault("JWT_AUDIENCE", "galaxy-api")
	internalAPIKey  = strings.TrimSpace(os.Getenv("INTERNAL_API_KEY"))
	llmServiceURL   = strings.TrimRight(envOrDefault("LLM_SERVICE_URL", "http://llm-service:8600"), "/")
	llmTimeout      = timeoutFromEnv("LLM_TIMEOUT", 2*time.Second)
	allowPublicRead = strings.EqualFold(envOrDefault("AUTHORITY_ALLOW_PUBLIC_READ", "false"), "true")
	authorityAddr   = envOrDefault("CHAIN_REST_ADDR", "0.0.0.0:1317")
	authorityDataDir = envOrDefault("CHAIN_DATA_DIR", "/data")
	eventLogPath    = filepath.Join(authorityDataDir, "events.jsonl")
)

func main() {
	if err := validateConfig(); err != nil {
		log.Fatalf("configuration error: %v", err)
	}
	if err := loadEvents(); err != nil {
		log.Fatalf("event ledger verification failed: %v", err)
	}
	startHTTPServer()
}

func envOrDefault(key, fallback string) string {
	value := strings.TrimSpace(os.Getenv(key))
	if value == "" {
		return fallback
	}
	return value
}

func timeoutFromEnv(key string, fallback time.Duration) time.Duration {
	raw := strings.TrimSpace(os.Getenv(key))
	if raw == "" {
		return fallback
	}
	if strings.IndexFunc(raw, func(r rune) bool { return r < '0' || r > '9' }) == -1 {
		if seconds, err := time.ParseDuration(raw + "s"); err == nil {
			return seconds
		}
	}
	if d, err := time.ParseDuration(raw); err == nil {
		return d
	}
	log.Printf("invalid duration for %s=%q, using fallback %s", key, raw, fallback)
	return fallback
}

func validateConfig() error {
	for name, value := range map[string]string{
		"JWT_SECRET":       jwtSecret,
		"INTERNAL_API_KEY": internalAPIKey,
	} {
		lower := strings.ToLower(value)
		if len(value) < 32 || strings.Contains(lower, "change-me") || strings.Contains(lower, "changeme") {
			return fmt.Errorf("%s must be a non-placeholder value of at least 32 characters", name)
		}
	}
	if authorityDataDir == "" {
		return errors.New("CHAIN_DATA_DIR is required")
	}
	return nil
}

func allowedWebSocketOrigin(r *http.Request) bool {
	origin := strings.TrimSpace(r.Header.Get("Origin"))
	if origin == "" {
		return !strings.EqualFold(envOrDefault("ENVIRONMENT", "production"), "production")
	}
	for _, allowed := range strings.Split(os.Getenv("AUTHORITY_WS_ALLOWED_ORIGINS"), ",") {
		if strings.TrimRight(strings.TrimSpace(allowed), "/") == strings.TrimRight(origin, "/") {
			return true
		}
	}
	return false
}

func securityHeaders(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("X-Content-Type-Options", "nosniff")
		w.Header().Set("X-Frame-Options", "DENY")
		w.Header().Set("Cache-Control", "no-store")
		next.ServeHTTP(w, r)
	})
}

func recordHash(event Event) (string, error) {
	copyEvent := event
	copyEvent.RecordHash = ""
	payload, err := json.Marshal(copyEvent)
	if err != nil {
		return "", err
	}
	sum := sha256.Sum256(payload)
	return hex.EncodeToString(sum[:]), nil
}

func loadEvents() error {
	if err := os.MkdirAll(authorityDataDir, 0o700); err != nil {
		return err
	}
	file, err := os.Open(eventLogPath)
	if errors.Is(err, os.ErrNotExist) {
		return nil
	}
	if err != nil {
		return err
	}
	defer file.Close()

	scanner := bufio.NewScanner(file)
	scanner.Buffer(make([]byte, 64<<10), 2<<20)
	expectedPrevious := ""
	lineNumber := 0
	for scanner.Scan() {
		lineNumber++
		var event Event
		if err := json.Unmarshal(scanner.Bytes(), &event); err != nil {
			return fmt.Errorf("line %d: invalid JSON: %w", lineNumber, err)
		}
		if event.PreviousHash != expectedPrevious {
			return fmt.Errorf("line %d: previous hash mismatch", lineNumber)
		}
		expectedHash, err := recordHash(event)
		if err != nil {
			return fmt.Errorf("line %d: hash error: %w", lineNumber, err)
		}
		if !hmac.Equal([]byte(event.RecordHash), []byte(expectedHash)) {
			return fmt.Errorf("line %d: record hash mismatch", lineNumber)
		}
		if _, exists := events[event.ID]; exists {
			return fmt.Errorf("line %d: duplicate event id", lineNumber)
		}
		events[event.ID] = event
		eventOrder = append(eventOrder, event.ID)
		expectedPrevious = event.RecordHash
	}
	if err := scanner.Err(); err != nil {
		return err
	}
	lastRecordHash = expectedPrevious
	log.Printf("verified authority ledger events=%d", len(eventOrder))
	return nil
}

func persistEventLocked(event *Event) error {
	event.PreviousHash = lastRecordHash
	hash, err := recordHash(*event)
	if err != nil {
		return err
	}
	event.RecordHash = hash

	file, err := os.OpenFile(eventLogPath, os.O_CREATE|os.O_WRONLY|os.O_APPEND, 0o600)
	if err != nil {
		return err
	}
	encoder := json.NewEncoder(file)
	if err := encoder.Encode(event); err != nil {
		_ = file.Close()
		return err
	}
	if err := file.Sync(); err != nil {
		_ = file.Close()
		return err
	}
	if err := file.Close(); err != nil {
		return err
	}
	lastRecordHash = event.RecordHash
	return nil
}

func startHTTPServer() {
	mux := http.NewServeMux()
	mux.HandleFunc("/health", healthHandler)
	mux.HandleFunc("/galaxy/v1/events", eventsHandler)
	mux.HandleFunc("/cosmos/tx/v1beta1/txs", cosmosTxsHandler)
	mux.HandleFunc("/websocket", wsHandler)
	mux.HandleFunc("/ws", wsHandler)

	server := &http.Server{
		Addr:              authorityAddr,
		Handler:           securityHeaders(mux),
		ReadHeaderTimeout: 5 * time.Second,
		ReadTimeout:       15 * time.Second,
		WriteTimeout:      30 * time.Second,
		IdleTimeout:       60 * time.Second,
		MaxHeaderBytes:    16 << 10,
	}
	log.Printf("HTTP server listening on %s", authorityAddr)
	log.Fatal(server.ListenAndServe())
}

func healthHandler(w http.ResponseWriter, _ *http.Request) {
	eventsLock.RLock()
	count := len(eventOrder)
	head := lastRecordHash
	eventsLock.RUnlock()
	writeJSON(w, http.StatusOK, map[string]any{
		"status": "ok",
		"service": "authority-ledger",
		"events": count,
		"ledger_head": head,
	})
}

func requestContextFromHTTP(r *http.Request) (requestContext, error) {
	if key := strings.TrimSpace(r.Header.Get("X-Internal-Auth")); key != "" {
		if len(internalAPIKey) >= 32 && hmac.Equal([]byte(key), []byte(internalAPIKey)) {
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

func websocketToken(r *http.Request) (string, string, error) {
	for _, item := range strings.Split(r.Header.Get("Sec-WebSocket-Protocol"), ",") {
		protocol := strings.TrimSpace(item)
		if strings.HasPrefix(protocol, "galaxy.jwt.") {
			token := strings.TrimPrefix(protocol, "galaxy.jwt.")
			if token != "" {
				return token, protocol, nil
			}
		}
	}
	return "", "", errors.New("websocket authentication protocol required")
}

func requestContextFromToken(token string) (requestContext, error) {
	parts := strings.Split(token, ".")
	if len(parts) != 3 {
		return requestContext{}, errors.New("invalid token")
	}

	headerBytes, err := base64.RawURLEncoding.DecodeString(parts[0])
	if err != nil {
		return requestContext{}, errors.New("invalid token header")
	}
	var header map[string]any
	if err := json.Unmarshal(headerBytes, &header); err != nil || header["alg"] != "HS256" {
		return requestContext{}, errors.New("unsupported token algorithm")
	}

	signingInput := parts[0] + "." + parts[1]
	providedSig, err := base64.RawURLEncoding.DecodeString(parts[2])
	if err != nil {
		return requestContext{}, errors.New("invalid token signature")
	}
	mac := hmac.New(sha256.New, []byte(jwtSecret))
	_, _ = mac.Write([]byte(signingInput))
	if !hmac.Equal(providedSig, mac.Sum(nil)) {
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

	if fmt.Sprint(claims["type"]) != "access" {
		return requestContext{}, errors.New("access token required")
	}
	if fmt.Sprint(claims["iss"]) != jwtIssuer {
		return requestContext{}, errors.New("invalid token issuer")
	}
	if fmt.Sprint(claims["aud"]) != jwtAudience {
		return requestContext{}, errors.New("invalid token audience")
	}
	for _, claim := range []string{"sub", "org_id", "jti"} {
		if strings.TrimSpace(fmt.Sprint(claims[claim])) == "" || fmt.Sprint(claims[claim]) == "<nil>" {
			return requestContext{}, fmt.Errorf("%s missing from token", claim)
		}
	}

	now := time.Now().UTC()
	exp, ok := toUnixSeconds(claims["exp"])
	if !ok || !time.Unix(exp, 0).After(now) {
		return requestContext{}, errors.New("token expired")
	}
	iat, ok := toUnixSeconds(claims["iat"])
	if !ok || time.Unix(iat, 0).After(now.Add(30*time.Second)) {
		return requestContext{}, errors.New("invalid token issued-at")
	}
	if nbfRaw, exists := claims["nbf"]; exists {
		nbf, valid := toUnixSeconds(nbfRaw)
		if !valid || time.Unix(nbf, 0).After(now.Add(30*time.Second)) {
			return requestContext{}, errors.New("token not active")
		}
	}

	return requestContext{OrgID: strings.TrimSpace(fmt.Sprint(claims["org_id"]))}, nil
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

func parseSubmission(body []byte) (Event, error) {
	var raw map[string]json.RawMessage
	if err := json.Unmarshal(body, &raw); err != nil {
		return Event{}, err
	}

	var event Event
	if _, ok := raw["event"]; ok {
		var submitted nestedSubmission
		decoder := json.NewDecoder(bytes.NewReader(body))
		decoder.DisallowUnknownFields()
		if err := decoder.Decode(&submitted); err != nil {
			return Event{}, err
		}
		event = Event{
			OrgID:        strings.TrimSpace(submitted.OrgID),
			Submitter:    strings.TrimSpace(submitted.Submitter),
			EnvelopeID:   strings.TrimSpace(submitted.EnvelopeID),
			OriginPeerID: strings.TrimSpace(submitted.OriginPeerID),
			DeviceID:     strings.TrimSpace(submitted.Event.DeviceID),
			EventType:    strings.TrimSpace(submitted.Event.EventType),
			Confidence:   submitted.Event.Confidence,
			Description:  strings.TrimSpace(submitted.Event.Description),
			Location:     strings.TrimSpace(submitted.Event.Location),
			FrameHash:    strings.TrimSpace(submitted.Event.FrameHash),
			Signature:    strings.TrimSpace(submitted.Event.Signature),
		}
	} else {
		var submitted simpleSubmission
		decoder := json.NewDecoder(bytes.NewReader(body))
		decoder.DisallowUnknownFields()
		if err := decoder.Decode(&submitted); err != nil {
			return Event{}, err
		}
		confidence := submitted.Confidence
		if submitted.ConfidenceF != 0 {
			confidence = submitted.ConfidenceF
		}
		event = Event{
			OrgID:        strings.TrimSpace(submitted.OrgID),
			Submitter:    strings.TrimSpace(submitted.Creator),
			EnvelopeID:   strings.TrimSpace(submitted.EnvelopeID),
			OriginPeerID: strings.TrimSpace(submitted.OriginPeerID),
			DeviceID:     strings.TrimSpace(submitted.DeviceID),
			EventType:    strings.TrimSpace(submitted.EventType),
			Confidence:   confidence,
			Description:  strings.TrimSpace(submitted.Description),
			Location:     strings.TrimSpace(submitted.Location),
			FrameHash:    strings.TrimSpace(submitted.FrameHash),
			Signature:    strings.TrimSpace(submitted.Signature),
		}
	}

	if err := validateEvent(event); err != nil {
		return Event{}, err
	}
	return event, nil
}

func validateEvent(event Event) error {
	if event.DeviceID == "" || len(event.DeviceID) > 255 {
		return errors.New("device_id is required and must be at most 255 characters")
	}
	if event.EventType == "" || len(event.EventType) > 100 {
		return errors.New("event_type is required and must be at most 100 characters")
	}
	if event.Confidence < 0 || event.Confidence > 1 {
		return errors.New("confidence must be between 0 and 1")
	}
	if len(event.Description) > 2000 || len(event.Location) > 255 {
		return errors.New("event text fields are too long")
	}
	if event.FrameHash != "" {
		decoded, err := hex.DecodeString(event.FrameHash)
		if err != nil || len(decoded) != sha256.Size {
			return errors.New("frame_hash must be a 32-byte hex value")
		}
	}
	if event.Signature != "" {
		decoded, err := hex.DecodeString(event.Signature)
		if err != nil || len(decoded) != sha256.Size {
			return errors.New("signature must be a 32-byte hex value")
		}
	}
	return nil
}

func clampConfidence(v float64) float64 {
	if v < 0 {
		return 0
	}
	if v > 1 {
		return 1
	}
	return v
}

func clampAdjustment(v float64) float64 {
	if v < -0.2 {
		return -0.2
	}
	if v > 0.2 {
		return 0.2
	}
	return v
}

func classifyEventConfidence(event Event) (float64, string, error) {
	if llmServiceURL == "" {
		return 0.0, "llm service disabled", nil
	}

	description := strings.TrimSpace(event.Description)
	if description == "" {
		description = fmt.Sprintf("event_type=%s location=%s device_id=%s", event.EventType, event.Location, event.DeviceID)
	}

	reqBody, _ := json.Marshal(map[string]any{
		"event_type":  event.EventType,
		"description": description,
	})

	req, err := http.NewRequest(http.MethodPost, llmServiceURL+"/classify", bytes.NewReader(reqBody))
	if err != nil {
		return 0.0, "classification request error", err
	}
	req.Header.Set("Content-Type", "application/json")
	if internalAPIKey != "" {
		req.Header.Set("X-Internal-Auth", internalAPIKey)
	}

	client := &http.Client{Timeout: llmTimeout}
	resp, err := client.Do(req)
	if err != nil {
		return 0.0, "classification service unavailable", err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(io.LimitReader(resp.Body, 256))
		return 0.0, "classification non-200 response", fmt.Errorf("status=%d body=%s", resp.StatusCode, strings.TrimSpace(string(body)))
	}

	var parsed struct {
		ConfidenceAdjustment float64 `json:"confidence_adjustment"`
		Reason               string  `json:"reason"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&parsed); err != nil {
		return 0.0, "classification parse error", err
	}

	return clampAdjustment(parsed.ConfidenceAdjustment), parsed.Reason, nil
}

func eventsHandler(w http.ResponseWriter, r *http.Request) {
	ctx := requestContext{}
	if r.Method == http.MethodGet && allowPublicRead {
		ctx = requestContext{Internal: true, OrgID: "public"}
	} else {
		resolvedCtx, err := requestContextFromHTTP(r)
		if err != nil {
			http.Error(w, "unauthorized", http.StatusUnauthorized)
			return
		}
		ctx = resolvedCtx
	}

	switch r.Method {
	case http.MethodGet:
		limit := 50
		if raw := r.URL.Query().Get("limit"); raw != "" {
			parsed, err := strconv.Atoi(raw)
			if err != nil || parsed < 1 || parsed > 200 {
				http.Error(w, "limit must be between 1 and 200", http.StatusBadRequest)
				return
			}
			limit = parsed
		}

		eventsLock.RLock()
		list := make([]Event, 0, limit)
		total := 0
		for index := len(eventOrder) - 1; index >= 0; index-- {
			event := events[eventOrder[index]]
			if !ctx.Internal && event.OrgID != ctx.OrgID {
				continue
			}
			total++
			if len(list) < limit {
				list = append(list, event)
			}
		}
		eventsLock.RUnlock()
		writeJSON(w, http.StatusOK, map[string]any{"events": list, "total": total})

	case http.MethodPost:
		if contentType := r.Header.Get("Content-Type"); !strings.HasPrefix(contentType, "application/json") {
			http.Error(w, "Content-Type must be application/json", http.StatusUnsupportedMediaType)
			return
		}
		r.Body = http.MaxBytesReader(w, r.Body, 1<<20)
		body, err := io.ReadAll(r.Body)
		if err != nil {
			http.Error(w, "failed to read body", http.StatusBadRequest)
			return
		}

		event, err := parseSubmission(body)
		if err != nil {
			http.Error(w, err.Error(), http.StatusBadRequest)
			return
		}
		if ctx.Internal {
			if event.OrgID == "" {
				http.Error(w, "org_id is required for internal submissions", http.StatusBadRequest)
				return
			}
		} else {
			event.OrgID = ctx.OrgID
		}
		if len(event.OrgID) > 128 {
			http.Error(w, "org_id is too long", http.StatusBadRequest)
			return
		}

		adjustment, reason, classifyErr := classifyEventConfidence(event)
		if classifyErr != nil {
			log.Printf("llm classify warning: %v", classifyErr)
		}
		event.Confidence = clampConfidence(event.Confidence + adjustment)
		event.LLMReason = reason
		if event.EnvelopeID != "" {
			event.ID = event.EnvelopeID
		} else {
			event.ID = time.Now().UTC().Format(time.RFC3339Nano)
		}
		event.Timestamp = time.Now().Unix()
		event.Status = "pending"

		eventsLock.Lock()
		if existing, exists := events[event.ID]; exists {
			eventsLock.Unlock()
			if existing.OrgID != event.OrgID {
				http.Error(w, "event id conflict", http.StatusConflict)
				return
			}
			writeJSON(w, http.StatusOK, map[string]any{
				"id": existing.ID,
				"status": existing.Status,
				"record_hash": existing.RecordHash,
				"idempotent": true,
			})
			return
		}
		if err := persistEventLocked(&event); err != nil {
			eventsLock.Unlock()
			log.Printf("ledger append failed: %v", err)
			http.Error(w, "ledger append failed", http.StatusInternalServerError)
			return
		}
		events[event.ID] = event
		eventOrder = append(eventOrder, event.ID)
		eventsLock.Unlock()

		broadcastEvent(event)
		writeJSON(w, http.StatusCreated, eventToResponse(event))

	default:
		w.Header().Set("Allow", "GET, POST")
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
	}
}

func eventToResponse(event Event) map[string]any {
	payload, _ := json.Marshal(event)
	var response map[string]any
	_ = json.Unmarshal(payload, &response)
	return response
}

func cosmosTxsHandler(w http.ResponseWriter, r *http.Request) {
	ctx, err := requestContextFromHTTP(r)
	if err != nil {
		http.Error(w, "unauthorized", http.StatusUnauthorized)
		return
	}
	if r.Method != http.MethodGet {
		w.Header().Set("Allow", "GET")
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
		return
	}

	eventsLock.RLock()
	rows := make([]Event, 0, len(eventOrder))
	for index := len(eventOrder) - 1; index >= 0; index-- {
		event := events[eventOrder[index]]
		if ctx.Internal || event.OrgID == ctx.OrgID {
			rows = append(rows, event)
		}
	}
	eventsLock.RUnlock()
	writeJSON(w, http.StatusOK, map[string]any{"txs": rows, "total": len(rows)})
}

func wsHandler(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
		return
	}
	token, protocol, err := websocketToken(r)
	if err != nil {
		http.Error(w, "unauthorized", http.StatusUnauthorized)
		return
	}
	ctx, err := requestContextFromToken(token)
	if err != nil {
		http.Error(w, "unauthorized", http.StatusUnauthorized)
		return
	}

	responseHeaders := http.Header{}
	responseHeaders.Set("Sec-WebSocket-Protocol", protocol)
	conn, err := wsUpgrader.Upgrade(w, r, responseHeaders)
	if err != nil {
		log.Printf("websocket upgrade error: %v", err)
		return
	}
	defer conn.Close()
	conn.SetReadLimit(64 << 10)

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


func writeJSON(w http.ResponseWriter, status int, payload any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	if err := json.NewEncoder(w).Encode(payload); err != nil {
		log.Printf("response encoding failed: %v", err)
	}
}
