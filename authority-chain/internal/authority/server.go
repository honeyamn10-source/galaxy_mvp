package authority

import (
	"bytes"
	"bufio"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"log"
	"net"
	"net/http"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"sync"
	"time"

	"github.com/gorilla/websocket"
	"google.golang.org/grpc"
	"google.golang.org/grpc/encoding"
)

type Config struct {
	ChainID              string
	GRPCAddr             string
	RESTAddr             string
	RPCAddr              string
	DataDir              string
	VoteThreshold        uint64
	VoteWindowSeconds    int64
	RewardAmountUGalaxy  int64
	SubmissionFeeUGalaxy int64
	AllowFeeOverdraft    bool
	AutoVerifyConfidence float64
	ComplianceURL        string
	ComplianceTimeout    time.Duration
	CosmWasmEnabled      bool
}

type EventPayload struct {
	DeviceID   string  `json:"device_id"`
	EventType  string  `json:"event_type"`
	Confidence float64 `json:"confidence"`
	Location   string  `json:"location,omitempty"`
	FrameHash  string  `json:"frame_hash,omitempty"`
	Signature  string  `json:"signature,omitempty"`
}

type StoredEvent struct {
	Height       int64        `json:"height"`
	TxHash       string       `json:"tx_hash"`
	ChainID      string       `json:"chain_id"`
	Creator      string       `json:"creator"`
	EnvelopeID   string       `json:"envelope_id"`
	OriginPeerID string       `json:"origin_peer_id"`
	Event        EventPayload `json:"event"`
	VotesYes     uint64       `json:"votes_yes"`
	VotesNo      uint64       `json:"votes_no"`
	Status       string       `json:"status"`
	VotingEnd    int64        `json:"voting_end"`
	CreatedAt    string       `json:"created_at"`
	UpdatedAt    string       `json:"updated_at"`
	RewardUGalaxy int64       `json:"reward_ugalaxy"`
	RewardPaid    bool        `json:"reward_paid"`
}

type EconomyState struct {
	PlanetRegistry map[string]string `json:"planet_registry"`
	Balances       map[string]int64  `json:"balances"`
	Stakes         map[string]int64  `json:"stakes"`
}

type planetRegisterRequest struct {
	DeviceID string `json:"device_id"`
	Wallet   string `json:"wallet"`
}

type stakeRequest struct {
	Wallet string `json:"wallet"`
	Amount int64  `json:"amount"`
}

type slashRequest struct {
	Wallet    string `json:"wallet"`
	Amount    int64  `json:"amount"`
	Reason    string `json:"reason"`
	Validator string `json:"validator,omitempty"`
}

type cosmwasmInstantiateRequest struct {
	CodeID int64             `json:"code_id"`
	Label  string            `json:"label"`
	Admin  string            `json:"admin,omitempty"`
	Msg    map[string]any    `json:"msg"`
}

type cosmwasmContractInfo struct {
	Address string `json:"address"`
	CodeID  int64  `json:"code_id"`
	Label   string `json:"label"`
	Admin   string `json:"admin,omitempty"`
}

type submitEventRequest struct {
	Creator      string  `json:"creator"`
	DeviceID     string  `json:"device_id"`
	EventType    string  `json:"event_type"`
	Confidence   uint64  `json:"confidence"`
	FrameHash    string  `json:"frame_hash,omitempty"`
	Signature    string  `json:"signature,omitempty"`
	EnvelopeID   string  `json:"envelope_id"`
	OriginPeerID string  `json:"origin_peer_id"`
	Location     string  `json:"location,omitempty"`
	ConfidenceF  float64 `json:"confidence_f,omitempty"`
}

type submitEventResponse struct {
	Code   int    `json:"code"`
	Height string `json:"height,omitempty"`
	TxHash string `json:"txhash,omitempty"`
	Status string `json:"status,omitempty"`
	Message string `json:"message,omitempty"`
}

type voteEventRequest struct {
	Validator string `json:"validator"`
	FrameHash string `json:"frame_hash"`
	Vote      uint32 `json:"vote"`
}

type voteEventResponse struct {
	Code    int    `json:"code"`
	Status  string `json:"status,omitempty"`
	Message string `json:"message,omitempty"`
}

type Server struct {
	cfg         Config
	grpcServer  *grpc.Server
	restServer  *http.Server
	rpcServer   *http.Server
	persistPath string
	economyPath string

	mu          sync.Mutex
	events      []StoredEvent
	byEnvelope  map[string]int
	byFrameHash map[string]int
	economy     EconomyState
	contracts   []cosmwasmContractInfo
	subs        map[*websocket.Conn]struct{}
}

func NewServerFromEnv() (*Server, error) {
	cfg := Config{
		ChainID:              envOrDefault("CHAIN_ID", "galaxy-1"),
		GRPCAddr:             envOrDefault("CHAIN_GRPC_ADDR", "0.0.0.0:9090"),
		RESTAddr:             envOrDefault("CHAIN_REST_ADDR", "0.0.0.0:1317"),
		RPCAddr:              envOrDefault("CHAIN_RPC_ADDR", "0.0.0.0:26657"),
		DataDir:              envOrDefault("CHAIN_DATA_DIR", "/data"),
		VoteThreshold:        parseUintEnv("CHAIN_VOTE_THRESHOLD", 2),
		VoteWindowSeconds:    parseInt64Env("CHAIN_VOTE_WINDOW_SECONDS", 3600),
		RewardAmountUGalaxy:  parseInt64Env("CHAIN_REWARD_UGALAXY", 100),
		SubmissionFeeUGalaxy: parseInt64Env("CHAIN_SUBMISSION_FEE_UGALAXY", 5),
		AllowFeeOverdraft:    parseBoolEnv("CHAIN_ALLOW_FEE_OVERDRAFT", true),
		AutoVerifyConfidence: parseFloatEnv("CHAIN_AUTO_VERIFY_CONFIDENCE", 0.90),
		ComplianceURL:        strings.TrimSpace(os.Getenv("CHAIN_COMPLIANCE_URL")),
		ComplianceTimeout:    parseDurationEnv("CHAIN_COMPLIANCE_TIMEOUT", 3*time.Second),
		CosmWasmEnabled:      parseBoolEnv("CHAIN_COSMWASM_ENABLED", true),
	}

	if err := os.MkdirAll(cfg.DataDir, 0o755); err != nil {
		return nil, fmt.Errorf("create chain data dir: %w", err)
	}

	s := &Server{
		cfg:         cfg,
		persistPath: filepath.Join(cfg.DataDir, "events.jsonl"),
		economyPath: filepath.Join(cfg.DataDir, "economy.json"),
		byEnvelope:  make(map[string]int),
		byFrameHash: make(map[string]int),
		economy: EconomyState{
			PlanetRegistry: make(map[string]string),
			Balances:       make(map[string]int64),
			Stakes:         make(map[string]int64),
		},
		subs:        make(map[*websocket.Conn]struct{}),
	}

	if err := s.loadPersisted(); err != nil {
		return nil, err
	}
	if err := s.loadEconomy(); err != nil {
		return nil, err
	}

	return s, nil
}

func (s *Server) Start(ctx context.Context) error {
	encoding.RegisterCodec(jsonCodec{})

	s.grpcServer = grpc.NewServer()
	registerMsgService(s.grpcServer, s)

	grpcLis, err := net.Listen("tcp", s.cfg.GRPCAddr)
	if err != nil {
		return fmt.Errorf("listen gRPC: %w", err)
	}

	restMux := http.NewServeMux()
	restMux.HandleFunc("/health", s.handleHealth)
	restMux.HandleFunc("/galaxy/v1/events", s.handleGalaxyEvents)
	restMux.HandleFunc("/cosmos/tx/v1beta1/txs", s.handleCosmosTxs)
	restMux.HandleFunc("/economy/v1/planet/register", s.handlePlanetRegister)
	restMux.HandleFunc("/economy/v1/balance/", s.handleWalletBalance)
	restMux.HandleFunc("/economy/v1/balance/by-device/", s.handleDeviceBalance)
	restMux.HandleFunc("/economy/v1/stake", s.handleStake)
	restMux.HandleFunc("/economy/v1/unstake", s.handleUnstake)
	restMux.HandleFunc("/economy/v1/slash", s.handleSlash)
	restMux.HandleFunc("/economy/v1/state", s.handleEconomyState)
	restMux.HandleFunc("/cosmwasm/wasm/v1/contracts", s.handleCosmWasmContracts)
	restMux.HandleFunc("/cosmwasm/wasm/v1/tx/instantiate", s.handleCosmWasmInstantiate)
	s.restServer = &http.Server{Addr: s.cfg.RESTAddr, Handler: restMux}

	rpcMux := http.NewServeMux()
	rpcMux.HandleFunc("/websocket", s.handleWebSocket)
	s.rpcServer = &http.Server{Addr: s.cfg.RPCAddr, Handler: rpcMux}

	errCh := make(chan error, 4)

	go func() {
		log.Printf("galaxyd gRPC listening on %s", s.cfg.GRPCAddr)
		errCh <- s.grpcServer.Serve(grpcLis)
	}()
	go func() {
		log.Printf("galaxyd REST listening on %s", s.cfg.RESTAddr)
		if err := s.restServer.ListenAndServe(); !errors.Is(err, http.ErrServerClosed) {
			errCh <- err
		}
	}()
	go func() {
		log.Printf("galaxyd RPC listening on %s", s.cfg.RPCAddr)
		if err := s.rpcServer.ListenAndServe(); !errors.Is(err, http.ErrServerClosed) {
			errCh <- err
		}
	}()
	go s.endBlockLoop(ctx)

	select {
	case <-ctx.Done():
		stopCtx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
		defer cancel()
		s.grpcServer.GracefulStop()
		_ = s.restServer.Shutdown(stopCtx)
		_ = s.rpcServer.Shutdown(stopCtx)
		return nil
	case err := <-errCh:
		return err
	}
}

func (s *Server) SubmitEvent(ctx context.Context, req *submitEventRequest) (*submitEventResponse, error) {
	if strings.TrimSpace(req.Creator) == "" {
		return &submitEventResponse{Code: 1, Message: "creator is required"}, nil
	}
	if strings.TrimSpace(req.DeviceID) == "" {
		return &submitEventResponse{Code: 1, Message: "device_id is required"}, nil
	}
	if strings.TrimSpace(req.EventType) == "" {
		return &submitEventResponse{Code: 1, Message: "event_type is required"}, nil
	}
	if strings.TrimSpace(req.EnvelopeID) == "" {
		return &submitEventResponse{Code: 1, Message: "envelope_id is required"}, nil
	}

	confidence := req.ConfidenceF
	if confidence <= 0 {
		confidence = float64(req.Confidence) / 100.0
	}
	if confidence < 0.0 || confidence > 1.0 {
		return &submitEventResponse{Code: 1, Message: "confidence must be between 0 and 1"}, nil
	}

	normalizedEvent := EventPayload{
		DeviceID:   req.DeviceID,
		EventType:  req.EventType,
		Confidence: confidence,
		Location:   req.Location,
		FrameHash:  req.FrameHash,
		Signature:  req.Signature,
	}

	if transformed, err := s.applyCompliance(ctx, req.Creator, normalizedEvent); err != nil {
		return &submitEventResponse{Code: 1, Message: fmt.Sprintf("compliance failed: %v", err)}, nil
	} else {
		normalizedEvent = transformed
	}

	s.mu.Lock()
	defer s.mu.Unlock()

	if idx, ok := s.byEnvelope[req.EnvelopeID]; ok {
		e := s.events[idx]
		return &submitEventResponse{Code: 0, Height: strconv.FormatInt(e.Height, 10), TxHash: e.TxHash, Status: e.Status}, nil
	}

	now := time.Now().UTC()
	height := int64(len(s.events) + 1)
	txhash := fmt.Sprintf("TX%012d", height)

	if s.cfg.SubmissionFeeUGalaxy > 0 {
		if s.economy.Balances[req.Creator] < s.cfg.SubmissionFeeUGalaxy {
			if !s.cfg.AllowFeeOverdraft {
				return &submitEventResponse{Code: 1, Message: "insufficient balance for submission fee"}, nil
			}
			log.Printf("submission fee skipped due to low balance creator=%s balance=%d fee=%d", req.Creator, s.economy.Balances[req.Creator], s.cfg.SubmissionFeeUGalaxy)
		} else {
			s.economy.Balances[req.Creator] -= s.cfg.SubmissionFeeUGalaxy
			_ = s.persistEconomy()
		}
	}

	e := StoredEvent{
		Height:       height,
		TxHash:       txhash,
		ChainID:      s.cfg.ChainID,
		Creator:      req.Creator,
		EnvelopeID:   req.EnvelopeID,
		OriginPeerID: req.OriginPeerID,
		Event:         normalizedEvent,
		VotesYes:      0,
		VotesNo:       0,
		Status:        "pending",
		VotingEnd:     now.Unix() + s.cfg.VoteWindowSeconds,
		CreatedAt:     now.Format(time.RFC3339),
		UpdatedAt:     now.Format(time.RFC3339),
		RewardUGalaxy: s.cfg.RewardAmountUGalaxy,
		RewardPaid:    false,
	}

	if e.Event.Confidence >= s.cfg.AutoVerifyConfidence {
		e.VotesYes = s.cfg.VoteThreshold
		e.Status = "verified"
		s.applyRewardLocked(&e)
	}

	s.events = append(s.events, e)
	idx := len(s.events) - 1
	s.byEnvelope[e.EnvelopeID] = idx
	if e.Event.FrameHash != "" {
		s.byFrameHash[e.Event.FrameHash] = idx
	}

	_ = s.appendPersisted(e)
	go s.broadcastTxEvent(e)

	return &submitEventResponse{Code: 0, Height: strconv.FormatInt(height, 10), TxHash: txhash, Status: e.Status}, nil
}

func (s *Server) VoteEvent(ctx context.Context, req *voteEventRequest) (*voteEventResponse, error) {
	if strings.TrimSpace(req.Validator) == "" {
		return &voteEventResponse{Code: 1, Message: "validator is required"}, nil
	}
	if strings.TrimSpace(req.FrameHash) == "" {
		return &voteEventResponse{Code: 1, Message: "frame_hash is required"}, nil
	}
	if req.Vote != 1 && req.Vote != 2 {
		return &voteEventResponse{Code: 1, Message: "vote must be 1 or 2"}, nil
	}

	s.mu.Lock()
	defer s.mu.Unlock()

	idx, ok := s.byFrameHash[req.FrameHash]
	if !ok {
		return &voteEventResponse{Code: 1, Message: "event not found"}, nil
	}

	e := s.events[idx]
	if req.Vote == 1 {
		e.VotesYes++
	} else {
		e.VotesNo++
	}
	e.UpdatedAt = time.Now().UTC().Format(time.RFC3339)
	if e.VotesYes >= s.cfg.VoteThreshold && e.VotesYes > e.VotesNo {
		e.Status = "verified"
		s.applyRewardLocked(&e)
	}
	s.events[idx] = e
	_ = s.rewritePersisted()

	return &voteEventResponse{Code: 0, Status: e.Status}, nil
}

func (s *Server) endBlockLoop(ctx context.Context) {
	ticker := time.NewTicker(2 * time.Second)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			now := time.Now().UTC().Unix()
			dirty := false

			s.mu.Lock()
			for i := range s.events {
				e := s.events[i]
				if e.Status != "pending" {
					continue
				}
				if now < e.VotingEnd {
					continue
				}
				if e.VotesYes >= s.cfg.VoteThreshold && e.VotesYes > e.VotesNo {
					e.Status = "verified"
					s.applyRewardLocked(&e)
				} else {
					e.Status = "rejected"
				}
				e.UpdatedAt = time.Now().UTC().Format(time.RFC3339)
				s.events[i] = e
				dirty = true
			}
			s.mu.Unlock()

			if dirty {
				_ = s.rewritePersisted()
			}
		}
	}
}

func (s *Server) handleHealth(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
		return
	}
	resp := map[string]any{
		"status":           "ok",
		"service":          "galaxyd",
		"chain_id":         s.cfg.ChainID,
		"grpc_addr":        s.cfg.GRPCAddr,
		"rest_addr":        s.cfg.RESTAddr,
		"rpc_addr":         s.cfg.RPCAddr,
		"events":           len(s.events),
		"cosmwasm_enabled": s.cfg.CosmWasmEnabled,
		"compliance_url":   s.cfg.ComplianceURL,
	}
	writeJSON(w, http.StatusOK, resp)
}

func (s *Server) handleGalaxyEvents(w http.ResponseWriter, r *http.Request) {
	switch r.Method {
	case http.MethodGet:
		limit := 50
		if v := r.URL.Query().Get("limit"); v != "" {
			if parsed, err := strconv.Atoi(v); err == nil && parsed > 0 {
				limit = parsed
			}
		}

		s.mu.Lock()
		rows := make([]StoredEvent, len(s.events))
		copy(rows, s.events)
		s.mu.Unlock()

		if len(rows) > limit {
			rows = rows[len(rows)-limit:]
		}
		reverse(rows)
		writeJSON(w, http.StatusOK, map[string]any{"events": rows, "total": len(s.events)})
	default:
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
	}
}

func (s *Server) handleCosmosTxs(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
		return
	}

	limit := 50
	if v := r.URL.Query().Get("limit"); v != "" {
		if parsed, err := strconv.Atoi(v); err == nil && parsed > 0 {
			limit = parsed
		}
	}

	s.mu.Lock()
	rows := make([]StoredEvent, len(s.events))
	copy(rows, s.events)
	s.mu.Unlock()

	if len(rows) > limit {
		rows = rows[len(rows)-limit:]
	}
	reverse(rows)

	txResponses := make([]map[string]any, 0, len(rows))
	txs := make([]map[string]any, 0, len(rows))
	for _, row := range rows {
		attrs := []map[string]any{
			{"key": "action", "value": "submit_event", "index": true},
			{"key": "module", "value": "galaxy", "index": true},
			{"key": "device_id", "value": row.Event.DeviceID, "index": true},
			{"key": "event_type", "value": row.Event.EventType, "index": true},
			{"key": "confidence", "value": strconv.Itoa(int(row.Event.Confidence * 100)), "index": true},
			{"key": "status", "value": row.Status, "index": true},
		}
		txResponses = append(txResponses, map[string]any{
			"txhash": row.TxHash,
			"height": strconv.FormatInt(row.Height, 10),
			"code": 0,
			"timestamp": row.CreatedAt,
			"events": []map[string]any{{"type": "message", "attributes": attrs}},
		})
		txs = append(txs, map[string]any{
			"body": map[string]any{
				"messages": []map[string]any{{
					"@type": "/galaxy.galaxy.MsgSubmitEvent",
					"creator": row.Creator,
					"device_id": row.Event.DeviceID,
					"event_type": row.Event.EventType,
					"confidence": int(row.Event.Confidence * 100),
					"frame_hash": row.Event.FrameHash,
					"signature": row.Event.Signature,
				}},
			},
		})
	}

	writeJSON(w, http.StatusOK, map[string]any{
		"tx_responses": txResponses,
		"txs": txs,
		"pagination": map[string]string{"total": strconv.Itoa(len(s.events))},
	})
}

func (s *Server) applyCompliance(ctx context.Context, tenant string, ev EventPayload) (EventPayload, error) {
	if s.cfg.ComplianceURL == "" {
		return ev, nil
	}

	payload := map[string]any{
		"tenant": tenant,
		"event":  ev,
	}
	bz, err := json.Marshal(payload)
	if err != nil {
		return EventPayload{}, err
	}

	reqCtx, cancel := context.WithTimeout(ctx, s.cfg.ComplianceTimeout)
	defer cancel()

	req, err := http.NewRequestWithContext(reqCtx, http.MethodPost, s.cfg.ComplianceURL+"/transform", bytes.NewReader(bz))
	if err != nil {
		return EventPayload{}, err
	}
	req.Header.Set("Content-Type", "application/json")

	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		return EventPayload{}, err
	}
	defer resp.Body.Close()

	if resp.StatusCode >= 300 {
		body, _ := io.ReadAll(io.LimitReader(resp.Body, 1024))
		return EventPayload{}, fmt.Errorf("compliance status=%d body=%s", resp.StatusCode, strings.TrimSpace(string(body)))
	}

	var transformed struct {
		Event EventPayload `json:"event"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&transformed); err != nil {
		return EventPayload{}, err
	}
	return transformed.Event, nil
}

func (s *Server) applyRewardLocked(e *StoredEvent) {
	if e.Status != "verified" || e.RewardPaid || e.RewardUGalaxy <= 0 {
		return
	}
	wallet := s.economy.PlanetRegistry[e.Event.DeviceID]
	if wallet == "" {
		wallet = e.Creator
	}
	s.economy.Balances[wallet] += e.RewardUGalaxy
	e.RewardPaid = true
	_ = s.persistEconomy()
}

func (s *Server) handlePlanetRegister(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
		return
	}

	var req planetRegisterRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "invalid json", http.StatusBadRequest)
		return
	}
	if strings.TrimSpace(req.DeviceID) == "" || strings.TrimSpace(req.Wallet) == "" {
		http.Error(w, "device_id and wallet are required", http.StatusBadRequest)
		return
	}

	s.mu.Lock()
	s.economy.PlanetRegistry[req.DeviceID] = req.Wallet
	if _, ok := s.economy.Balances[req.Wallet]; !ok {
		s.economy.Balances[req.Wallet] = 1000
	}
	err := s.persistEconomy()
	s.mu.Unlock()
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	writeJSON(w, http.StatusOK, map[string]any{"status": "ok", "device_id": req.DeviceID, "wallet": req.Wallet})
}

func (s *Server) handleWalletBalance(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
		return
	}
	wallet := strings.TrimSpace(strings.TrimPrefix(r.URL.Path, "/economy/v1/balance/"))
	if wallet == "" {
		http.Error(w, "wallet path parameter is required", http.StatusBadRequest)
		return
	}

	s.mu.Lock()
	balance := s.economy.Balances[wallet]
	staked := s.economy.Stakes[wallet]
	s.mu.Unlock()

	writeJSON(w, http.StatusOK, map[string]any{"wallet": wallet, "balance": balance, "staked": staked})
}

func (s *Server) handleDeviceBalance(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
		return
	}
	deviceID := strings.TrimSpace(strings.TrimPrefix(r.URL.Path, "/economy/v1/balance/by-device/"))
	if deviceID == "" {
		http.Error(w, "device_id path parameter is required", http.StatusBadRequest)
		return
	}

	s.mu.Lock()
	wallet := s.economy.PlanetRegistry[deviceID]
	balance := int64(0)
	staked := int64(0)
	if wallet != "" {
		balance = s.economy.Balances[wallet]
		staked = s.economy.Stakes[wallet]
	}
	s.mu.Unlock()

	writeJSON(w, http.StatusOK, map[string]any{
		"device_id": deviceID,
		"wallet":    wallet,
		"balance":   balance,
		"staked":    staked,
	})
}

func (s *Server) handleStake(w http.ResponseWriter, r *http.Request) {
	s.handleStakeAction(w, r, true)
}

func (s *Server) handleUnstake(w http.ResponseWriter, r *http.Request) {
	s.handleStakeAction(w, r, false)
}

func (s *Server) handleStakeAction(w http.ResponseWriter, r *http.Request, stake bool) {
	if r.Method != http.MethodPost {
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
		return
	}

	var req stakeRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "invalid json", http.StatusBadRequest)
		return
	}
	req.Wallet = strings.TrimSpace(req.Wallet)
	if req.Wallet == "" || req.Amount <= 0 {
		http.Error(w, "wallet and positive amount are required", http.StatusBadRequest)
		return
	}

	s.mu.Lock()
	defer s.mu.Unlock()

	if stake {
		if s.economy.Balances[req.Wallet] < req.Amount {
			http.Error(w, "insufficient balance", http.StatusBadRequest)
			return
		}
		s.economy.Balances[req.Wallet] -= req.Amount
		s.economy.Stakes[req.Wallet] += req.Amount
	} else {
		if s.economy.Stakes[req.Wallet] < req.Amount {
			http.Error(w, "insufficient staked amount", http.StatusBadRequest)
			return
		}
		s.economy.Stakes[req.Wallet] -= req.Amount
		s.economy.Balances[req.Wallet] += req.Amount
	}

	if err := s.persistEconomy(); err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"wallet": req.Wallet, "balance": s.economy.Balances[req.Wallet], "staked": s.economy.Stakes[req.Wallet]})
}

func (s *Server) handleSlash(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
		return
	}
	var req slashRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "invalid json", http.StatusBadRequest)
		return
	}
	req.Wallet = strings.TrimSpace(req.Wallet)
	if req.Wallet == "" || req.Amount <= 0 {
		http.Error(w, "wallet and positive amount are required", http.StatusBadRequest)
		return
	}

	s.mu.Lock()
	if s.economy.Stakes[req.Wallet] < req.Amount {
		s.mu.Unlock()
		http.Error(w, "insufficient staked amount", http.StatusBadRequest)
		return
	}
	s.economy.Stakes[req.Wallet] -= req.Amount
	err := s.persistEconomy()
	remaining := s.economy.Stakes[req.Wallet]
	s.mu.Unlock()
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	log.Printf("stake slashed wallet=%s amount=%d validator=%s reason=%s", req.Wallet, req.Amount, req.Validator, req.Reason)
	writeJSON(w, http.StatusOK, map[string]any{"wallet": req.Wallet, "staked": remaining, "slashed": req.Amount})
}

func (s *Server) handleEconomyState(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
		return
	}
	s.mu.Lock()
	state := s.economy
	s.mu.Unlock()
	writeJSON(w, http.StatusOK, state)
}

func (s *Server) handleCosmWasmContracts(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
		return
	}
	if !s.cfg.CosmWasmEnabled {
		http.Error(w, "cosmwasm disabled", http.StatusNotImplemented)
		return
	}

	s.mu.Lock()
	contracts := make([]cosmwasmContractInfo, len(s.contracts))
	copy(contracts, s.contracts)
	s.mu.Unlock()

	writeJSON(w, http.StatusOK, map[string]any{"contracts": contracts})
}

func (s *Server) handleCosmWasmInstantiate(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
		return
	}
	if !s.cfg.CosmWasmEnabled {
		http.Error(w, "cosmwasm disabled", http.StatusNotImplemented)
		return
	}

	var req cosmwasmInstantiateRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "invalid json", http.StatusBadRequest)
		return
	}
	if req.CodeID <= 0 || strings.TrimSpace(req.Label) == "" {
		http.Error(w, "code_id and label are required", http.StatusBadRequest)
		return
	}

	s.mu.Lock()
	addr := fmt.Sprintf("galaxy1contract%06d", len(s.contracts)+1)
	contract := cosmwasmContractInfo{Address: addr, CodeID: req.CodeID, Label: req.Label, Admin: req.Admin}
	s.contracts = append(s.contracts, contract)
	s.mu.Unlock()

	writeJSON(w, http.StatusOK, map[string]any{"address": addr, "code_id": req.CodeID, "label": req.Label})
}

var upgrader = websocket.Upgrader{CheckOrigin: func(r *http.Request) bool { return true }}

func (s *Server) handleWebSocket(w http.ResponseWriter, r *http.Request) {
	conn, err := upgrader.Upgrade(w, r, nil)
	if err != nil {
		return
	}
	s.mu.Lock()
	s.subs[conn] = struct{}{}
	s.mu.Unlock()

	defer func() {
		s.mu.Lock()
		delete(s.subs, conn)
		s.mu.Unlock()
		_ = conn.Close()
	}()

	for {
		_, data, err := conn.ReadMessage()
		if err != nil {
			return
		}
		var req map[string]any
		_ = json.Unmarshal(data, &req)
		if method, _ := req["method"].(string); method == "subscribe" {
			_ = conn.WriteJSON(map[string]any{
				"jsonrpc": "2.0",
				"id": req["id"],
				"result": map[string]any{},
			})
		} else {
			_ = conn.WriteJSON(map[string]any{"jsonrpc": "2.0", "id": "ping", "result": map[string]any{"ok": true}})
		}
	}
}

func (s *Server) broadcastTxEvent(e StoredEvent) {
	payload := map[string]any{
		"jsonrpc": "2.0",
		"id": "galaxy-sub",
		"result": map[string]any{
			"query": "tm.event='Tx' AND message.action='submit_event'",
			"data": map[string]any{
				"type": "tendermint/event/Tx",
				"value": map[string]any{
					"TxResult": map[string]any{
						"height": strconv.FormatInt(e.Height, 10),
						"result": map[string]any{
							"events": map[string]any{
								"message.action": []string{"submit_event"},
								"message.module": []string{"galaxy"},
								"galaxy.device_id": []string{e.Event.DeviceID},
								"galaxy.event_type": []string{e.Event.EventType},
								"galaxy.status": []string{e.Status},
								"galaxy.envelope_id": []string{e.EnvelopeID},
							},
						},
					},
				},
			},
		},
	}

	s.mu.Lock()
	defer s.mu.Unlock()
	for conn := range s.subs {
		_ = conn.WriteJSON(payload)
	}
}

func (s *Server) loadPersisted() error {
	file, err := os.Open(s.persistPath)
	if err != nil {
		if os.IsNotExist(err) {
			return nil
		}
		return fmt.Errorf("open persisted events: %w", err)
	}
	defer file.Close()

	scanner := bufio.NewScanner(file)
	for scanner.Scan() {
		line := strings.TrimSpace(scanner.Text())
		if line == "" {
			continue
		}
		var e StoredEvent
		if err := json.Unmarshal([]byte(line), &e); err != nil {
			continue
		}
		s.byEnvelope[e.EnvelopeID] = len(s.events)
		if e.Event.FrameHash != "" {
			s.byFrameHash[e.Event.FrameHash] = len(s.events)
		}
		s.events = append(s.events, e)
	}
	return scanner.Err()
}

func (s *Server) appendPersisted(e StoredEvent) error {
	f, err := os.OpenFile(s.persistPath, os.O_CREATE|os.O_APPEND|os.O_WRONLY, 0o644)
	if err != nil {
		return err
	}
	defer f.Close()
	b, _ := json.Marshal(e)
	_, err = f.Write(append(b, '\n'))
	return err
}

func (s *Server) rewritePersisted() error {
	f, err := os.Create(s.persistPath)
	if err != nil {
		return err
	}
	defer f.Close()
	enc := json.NewEncoder(f)
	for _, e := range s.events {
		if err := enc.Encode(e); err != nil {
			return err
		}
	}
	return nil
}

func (s *Server) loadEconomy() error {
	bz, err := os.ReadFile(s.economyPath)
	if err != nil {
		if os.IsNotExist(err) {
			return s.persistEconomy()
		}
		return fmt.Errorf("read economy state: %w", err)
	}

	var state EconomyState
	if err := json.Unmarshal(bz, &state); err != nil {
		return fmt.Errorf("decode economy state: %w", err)
	}

	if state.PlanetRegistry == nil {
		state.PlanetRegistry = make(map[string]string)
	}
	if state.Balances == nil {
		state.Balances = make(map[string]int64)
	}
	if state.Stakes == nil {
		state.Stakes = make(map[string]int64)
	}

	s.economy = state
	return nil
}

func (s *Server) persistEconomy() error {
	bz, err := json.MarshalIndent(s.economy, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(s.economyPath, bz, 0o644)
}

type jsonCodec struct{}

func (jsonCodec) Name() string { return "json" }

func (jsonCodec) Marshal(v interface{}) ([]byte, error) { return json.Marshal(v) }

func (jsonCodec) Unmarshal(data []byte, v interface{}) error { return json.Unmarshal(data, v) }

type msgServiceServer interface {
	SubmitEvent(context.Context, *submitEventRequest) (*submitEventResponse, error)
	VoteEvent(context.Context, *voteEventRequest) (*voteEventResponse, error)
}

func registerMsgService(grpcServer *grpc.Server, svc *Server) {
	submitHandler := grpc.UnaryHandler(func(ctx context.Context, req interface{}) (interface{}, error) {
		return svc.SubmitEvent(ctx, req.(*submitEventRequest))
	})
	voteHandler := grpc.UnaryHandler(func(ctx context.Context, req interface{}) (interface{}, error) {
		return svc.VoteEvent(ctx, req.(*voteEventRequest))
	})

	grpcServer.RegisterService(&grpc.ServiceDesc{
		ServiceName: "galaxy.galaxy.Msg",
		HandlerType: (*msgServiceServer)(nil),
		Methods: []grpc.MethodDesc{
			{
				MethodName: "SubmitEvent",
				Handler: func(_ interface{}, ctx context.Context, dec func(interface{}) error, _ grpc.UnaryServerInterceptor) (interface{}, error) {
					in := new(submitEventRequest)
					if err := dec(in); err != nil {
						return nil, err
					}
					return submitHandler(ctx, in)
				},
			},
			{
				MethodName: "VoteEvent",
				Handler: func(_ interface{}, ctx context.Context, dec func(interface{}) error, _ grpc.UnaryServerInterceptor) (interface{}, error) {
					in := new(voteEventRequest)
					if err := dec(in); err != nil {
						return nil, err
					}
					return voteHandler(ctx, in)
				},
			},
		},
	}, svc)
}

func reverse[T any](s []T) {
	for i, j := 0, len(s)-1; i < j; i, j = i+1, j-1 {
		s[i], s[j] = s[j], s[i]
	}
}

func writeJSON(w http.ResponseWriter, code int, payload any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(code)
	_ = json.NewEncoder(w).Encode(payload)
}

func envOrDefault(key, fallback string) string {
	if v := strings.TrimSpace(os.Getenv(key)); v != "" {
		return v
	}
	return fallback
}

func parseUintEnv(key string, fallback uint64) uint64 {
	v := strings.TrimSpace(os.Getenv(key))
	if v == "" {
		return fallback
	}
	n, err := strconv.ParseUint(v, 10, 64)
	if err != nil {
		return fallback
	}
	return n
}

func parseInt64Env(key string, fallback int64) int64 {
	v := strings.TrimSpace(os.Getenv(key))
	if v == "" {
		return fallback
	}
	n, err := strconv.ParseInt(v, 10, 64)
	if err != nil {
		return fallback
	}
	return n
}

func parseFloatEnv(key string, fallback float64) float64 {
	v := strings.TrimSpace(os.Getenv(key))
	if v == "" {
		return fallback
	}
	n, err := strconv.ParseFloat(v, 64)
	if err != nil {
		return fallback
	}
	return n
}

func parseBoolEnv(key string, fallback bool) bool {
	v := strings.TrimSpace(strings.ToLower(os.Getenv(key)))
	if v == "" {
		return fallback
	}
	switch v {
	case "1", "true", "yes", "y", "on":
		return true
	case "0", "false", "no", "n", "off":
		return false
	default:
		return fallback
	}
}

func parseDurationEnv(key string, fallback time.Duration) time.Duration {
	v := strings.TrimSpace(os.Getenv(key))
	if v == "" {
		return fallback
	}
	d, err := time.ParseDuration(v)
	if err != nil {
		return fallback
	}
	return d
}
