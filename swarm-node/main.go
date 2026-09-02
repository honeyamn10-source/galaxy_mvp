package main

import (
	"bytes"
	"context"
	"crypto/ed25519"
	"crypto/hmac"
	"crypto/sha256"
	"crypto/tls"
	"crypto/x509"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"log"
	"net"
	"net/http"
	"os"
	"os/signal"
	"strconv"
	"strings"
	"sync"
	"syscall"
	"time"

	libp2p "github.com/libp2p/go-libp2p"
	dht "github.com/libp2p/go-libp2p-kad-dht"
	pubsub "github.com/libp2p/go-libp2p-pubsub"
	"github.com/libp2p/go-libp2p/core/crypto"
	"github.com/libp2p/go-libp2p/core/host"
	"github.com/libp2p/go-libp2p/core/peer"
	"github.com/libp2p/go-libp2p/p2p/discovery/routing"
	"github.com/libp2p/go-libp2p/p2p/discovery/util"
	"github.com/libp2p/go-libp2p/p2p/security/noise"
	libp2ptls "github.com/libp2p/go-libp2p/p2p/security/tls"
	ma "github.com/multiformats/go-multiaddr"
	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promhttp"
	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"
	"google.golang.org/grpc/encoding"
)

const (
	eventTopicName      = "galaxy.events.v1"
	predictionTopicName = "galaxy.predictions.v1"
	defaultForwardTO    = 8 * time.Second
)

// Prometheus metrics
var (
	eventsIngested = prometheus.NewCounter(
		prometheus.CounterOpts{
			Name: "swarm_node_events_ingested_total",
			Help: "Total events ingested by the swarm node",
		},
	)
	eventsForwarded = prometheus.NewCounter(
		prometheus.CounterOpts{
			Name: "swarm_node_events_forwarded_total",
			Help: "Total events forwarded by the swarm node",
		},
	)
	peerCount = prometheus.NewGauge(
		prometheus.GaugeOpts{
			Name: "swarm_node_connected_peers",
			Help: "Number of connected peer nodes",
		},
	)
)

func init() {
	prometheus.MustRegister(eventsIngested)
	prometheus.MustRegister(eventsForwarded)
	prometheus.MustRegister(peerCount)
}

type Config struct {
	NodeName            string
	IdentitySeed        string
	AuthServiceURL      string
	InternalAPIKey      string
	RequireEventSignature bool
	EnforceDeviceBinding bool
	ListenPort          int
	IngressAddr         string
	HealthAddr          string
	Rendezvous          string
	BootstrapPeers      []string
	BootstrapSeeds      []string
	ForwardMode         string
	CreatorAddress      string
	BackendURL          string
	ValidatorSubmitURL  string
	ValidatorGRPCAddr   string
	RedispatchTimeout   time.Duration
	ServerCertPath      string
	ServerKeyPath       string
	ClientCAPath        string
	BackendHTTPTimeout  time.Duration
	ValidatorGRPCTimeout time.Duration
	DiscoveryInterval   time.Duration
}

type EventPayload struct {
	DeviceID   string  `json:"device_id"`
	EventType  string  `json:"event_type"`
	Confidence float64 `json:"confidence"`
	Location   string  `json:"location,omitempty"`
	FrameHash  string  `json:"frame_hash,omitempty"`
	Signature  string  `json:"signature,omitempty"`
}

type IngressRequest struct {
	APIKey string       `json:"api_key"`
	Event  EventPayload `json:"event"`
}

type PredictionIngressRequest struct {
	APIKey     string         `json:"api_key"`
	Prediction map[string]any `json:"prediction"`
}

type SwarmEnvelope struct {
	EnvelopeID   string       `json:"envelope_id"`
	APIKey       string       `json:"-"`
	OrgID        string       `json:"org_id"`
	KeyID        string       `json:"key_id,omitempty"`
	Event        EventPayload `json:"event"`
	OriginPeerID string       `json:"origin_peer_id"`
	CreatedAt    time.Time    `json:"created_at"`
}

type resolvedAPIKey struct {
	OrgID    string `json:"org_id"`
	DeviceID string `json:"device_id"`
	KeyID    string `json:"key_id"`
}

type App struct {
	cfg         Config
	host        host.Host
	dht         *dht.IpfsDHT
	pubSub      *pubsub.PubSub
	eventTopic  *pubsub.Topic
	eventSub    *pubsub.Subscription
	predTopic   *pubsub.Topic
	predSub     *pubsub.Subscription
	httpClient  *http.Client
	seenMu      sync.Mutex
	seen        map[string]time.Time
}

func main() {
	cfg, err := loadConfig()
	if err != nil {
		log.Fatalf("config error: %v", err)
	}

	ctx, cancel := signal.NotifyContext(context.Background(), syscall.SIGINT, syscall.SIGTERM)
	defer cancel()

	app, err := newApp(ctx, cfg)
	if err != nil {
		log.Fatalf("startup error: %v", err)
	}
	defer app.close()

	go app.discoveryLoop(ctx)
	go app.subscriptionLoop(ctx, app.eventSub, "event")
	go app.subscriptionLoop(ctx, app.predSub, "prediction")
	go app.cleanupLoop(ctx)

	if err := app.runHTTPServers(ctx); err != nil {
		log.Fatalf("http server error: %v", err)
	}
}

func loadConfig() (Config, error) {
	listenPort, err := parseIntEnv("SWARM_P2P_PORT", 7001)
	if err != nil {
		return Config{}, err
	}

	cfg := Config{
		NodeName:           envOrDefault("SWARM_NODE_NAME", "swarm-node"),
		IdentitySeed:       strings.TrimSpace(os.Getenv("SWARM_IDENTITY_SEED")),
		AuthServiceURL:     envOrDefault("AUTH_SERVICE_URL", "http://auth-service:8700"),
		InternalAPIKey:     strings.TrimSpace(os.Getenv("INTERNAL_API_KEY")),
		RequireEventSignature: envBool("SWARM_REQUIRE_EVENT_SIGNATURE", true),
		EnforceDeviceBinding: envBool("SWARM_ENFORCE_DEVICE_BINDING", true),
		ListenPort:         listenPort,
		IngressAddr:        envOrDefault("SWARM_INGRESS_ADDR", ":8443"),
		HealthAddr:         envOrDefault("SWARM_HEALTH_ADDR", ":8081"),
		Rendezvous:         envOrDefault("SWARM_RENDEZVOUS", "galaxy-v2"),
		BootstrapPeers:     splitCSV(os.Getenv("SWARM_BOOTSTRAP_PEERS")),
		BootstrapSeeds:     splitCSV(os.Getenv("SWARM_BOOTSTRAP_SEEDS")),
		ForwardMode:        envOrDefault("SWARM_FORWARD_MODE", "backend-http"),
		CreatorAddress:     envOrDefault("SWARM_CREATOR_ADDRESS", "galaxy1swarmsubmitter"),
		BackendURL:         envOrDefault("BACKEND_EVENTS_URL", "http://authority:8000/events"),
		ValidatorSubmitURL: envOrDefault("VALIDATOR_HTTP_URL", envOrDefault("VALIDATOR_SUBMIT_URL", "http://galaxyd:1317/galaxy/v1/events")),
		ValidatorGRPCAddr:  envOrDefault("VALIDATOR_GRPC_ADDR", "galaxyd:9090"),
		ServerCertPath:     envOrDefault("SWARM_TLS_CERT", "/certs/swarm-node.crt"),
		ServerKeyPath:      envOrDefault("SWARM_TLS_KEY", "/certs/swarm-node.key"),
		ClientCAPath:       envOrDefault("SWARM_CLIENT_CA", "/certs/ca.crt"),
		BackendHTTPTimeout: parseDurationEnv("SWARM_BACKEND_TIMEOUT", defaultForwardTO),
		ValidatorGRPCTimeout: parseDurationEnv("SWARM_VALIDATOR_GRPC_TIMEOUT", 5*time.Second),
		DiscoveryInterval:  parseDurationEnv("SWARM_DISCOVERY_INTERVAL", 20*time.Second),
		RedispatchTimeout:  parseDurationEnv("SWARM_REDISPATCH_TIMEOUT", 2*time.Minute),
	}

	if len(cfg.IdentitySeed) < 32 {
		return Config{}, errors.New("SWARM_IDENTITY_SEED must be at least 32 characters")
	}
	if len(cfg.InternalAPIKey) < 32 || strings.Contains(strings.ToLower(cfg.InternalAPIKey), "change-me") {
		return Config{}, errors.New("INTERNAL_API_KEY must be a non-placeholder value of at least 32 characters")
	}
	if cfg.AuthServiceURL == "" {
		return Config{}, errors.New("AUTH_SERVICE_URL is required")
	}
	if cfg.ForwardMode == "backend-http" && cfg.BackendURL == "" {
		return Config{}, errors.New("BACKEND_EVENTS_URL is required for backend-http mode")
	}
	if (cfg.ForwardMode == "validator-rest" || cfg.ForwardMode == "validator-http" || cfg.ForwardMode == "http") && cfg.ValidatorSubmitURL == "" {
		return Config{}, errors.New("VALIDATOR_SUBMIT_URL is required for validator-rest mode")
	}
	if cfg.ForwardMode == "validator-grpc" {
		return Config{}, errors.New("validator-grpc mode is disabled until transport TLS is configured; use validator-http")
	}

	return cfg, nil
}

func newApp(ctx context.Context, cfg Config) (*App, error) {
	priv, err := keyFromSeed(cfg.IdentitySeed)
	if err != nil {
		return nil, fmt.Errorf("identity key: %w", err)
	}

	listenAddr, err := ma.NewMultiaddr(fmt.Sprintf("/ip4/0.0.0.0/tcp/%d", cfg.ListenPort))
	if err != nil {
		return nil, fmt.Errorf("listen multiaddr: %w", err)
	}

	h, err := libp2p.New(
		libp2p.ListenAddrs(listenAddr),
		libp2p.Identity(priv),
		libp2p.Security(noise.ID, noise.New),
		libp2p.Security(libp2ptls.ID, libp2ptls.New),
		libp2p.NATPortMap(),
		libp2p.EnableRelay(),
		libp2p.EnableHolePunching(),
	)
	if err != nil {
		return nil, fmt.Errorf("libp2p host: %w", err)
	}

	kad, err := dht.New(ctx, h, dht.Mode(dht.ModeAutoServer))
	if err != nil {
		return nil, fmt.Errorf("dht init: %w", err)
	}

	if err := kad.Bootstrap(ctx); err != nil {
		return nil, fmt.Errorf("dht bootstrap: %w", err)
	}

	ps, err := pubsub.NewGossipSub(ctx, h,
		pubsub.WithPeerExchange(true),
		pubsub.WithFloodPublish(true),
	)
	if err != nil {
		return nil, fmt.Errorf("gossipsub init: %w", err)
	}

	eventTopic, err := ps.Join(eventTopicName)
	if err != nil {
		return nil, fmt.Errorf("event topic join: %w", err)
	}

	eventSub, err := eventTopic.Subscribe()
	if err != nil {
		return nil, fmt.Errorf("event topic subscribe: %w", err)
	}

	predTopic, err := ps.Join(predictionTopicName)
	if err != nil {
		return nil, fmt.Errorf("prediction topic join: %w", err)
	}

	predSub, err := predTopic.Subscribe()
	if err != nil {
		return nil, fmt.Errorf("prediction topic subscribe: %w", err)
	}

	app := &App{
		cfg:    cfg,
		host:   h,
		dht:    kad,
		pubSub: ps,
		eventTopic: eventTopic,
		eventSub:   eventSub,
		predTopic:  predTopic,
		predSub:    predSub,
		httpClient: &http.Client{
			Timeout: cfg.BackendHTTPTimeout,
		},
		seen: make(map[string]time.Time),
	}

	app.logAddresses()

	if err := app.connectBootstrap(ctx); err != nil {
		log.Printf("bootstrap warning: %v", err)
	}

	return app, nil
}

func (a *App) logAddresses() {
	log.Printf("node=%s peer_id=%s", a.cfg.NodeName, a.host.ID())
	for _, addr := range a.host.Addrs() {
		log.Printf("listening on %s/p2p/%s", addr, a.host.ID())
	}
}

func (a *App) connectBootstrap(ctx context.Context) error {
	var errs []string

	for _, raw := range a.cfg.BootstrapPeers {
		if err := a.connectPeerAddr(ctx, raw); err != nil {
			errs = append(errs, fmt.Sprintf("%s: %v", raw, err))
		}
	}

	for _, seedSpec := range a.cfg.BootstrapSeeds {
		info, err := peerInfoFromSeedSpec(seedSpec)
		if err != nil {
			errs = append(errs, fmt.Sprintf("%s: %v", seedSpec, err))
			continue
		}
		if err := a.host.Connect(ctx, *info); err != nil {
			errs = append(errs, fmt.Sprintf("%s: %v", seedSpec, err))
		} else {
			log.Printf("connected to bootstrap seed peer=%s", info.ID)
		}
	}

	if len(errs) > 0 {
		return errors.New(strings.Join(errs, "; "))
	}

	return nil
}

func (a *App) connectPeerAddr(ctx context.Context, raw string) error {
	maddr, err := ma.NewMultiaddr(raw)
	if err != nil {
		return fmt.Errorf("invalid multiaddr: %w", err)
	}
	info, err := peer.AddrInfoFromP2pAddr(maddr)
	if err != nil {
		return fmt.Errorf("parse addr info: %w", err)
	}
	if err := a.host.Connect(ctx, *info); err != nil {
		return fmt.Errorf("connect failed: %w", err)
	}
	log.Printf("connected to bootstrap peer=%s", info.ID)
	return nil
}

func (a *App) discoveryLoop(ctx context.Context) {
	routingDiscovery := routing.NewRoutingDiscovery(a.dht)
	util.Advertise(ctx, routingDiscovery, a.cfg.Rendezvous)

	ticker := time.NewTicker(a.cfg.DiscoveryInterval)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			peers, err := routingDiscovery.FindPeers(ctx, a.cfg.Rendezvous)
			if err != nil {
				log.Printf("discovery error: %v", err)
				continue
			}
			for p := range peers {
				if p.ID == a.host.ID() {
					continue
				}
				if err := a.host.Connect(ctx, p); err != nil {
					log.Printf("peer connect failed id=%s err=%v", p.ID, err)
				}
			}
		}
	}
}

func (a *App) subscriptionLoop(ctx context.Context, sub *pubsub.Subscription, topicType string) {
	for {
		msg, err := sub.Next(ctx)
		if err != nil {
			if ctx.Err() != nil {
				return
			}
			log.Printf("subscription read error topic=%s err=%v", topicType, err)
			continue
		}

		var envelope SwarmEnvelope
		if err := json.Unmarshal(msg.Data, &envelope); err != nil {
			log.Printf("invalid envelope received topic=%s err=%v", topicType, err)
			continue
		}

		if !a.markSeen(envelope.EnvelopeID) {
			continue
		}

		// The origin node forwards synchronously before publishing. Peers consume
		// the sanitized envelope for mesh visibility without duplicating writes.
		continue
	}
}

func (a *App) runHTTPServers(ctx context.Context) error {
	handler := http.NewServeMux()
	handler.HandleFunc("/healthz", a.handleHealth)
	handler.HandleFunc("/ingest", a.handleIngest)
	handler.HandleFunc("/ingest-prediction", a.handleIngestPrediction)
	handler.Handle("/metrics", promhttp.Handler())

	tlsCfg, err := a.serverTLSConfig()
	if err != nil {
		return fmt.Errorf("tls config: %w", err)
	}

	ingressSrv := &http.Server{
		Addr:              a.cfg.IngressAddr,
		Handler:           handler,
		TLSConfig:         tlsCfg,
		ReadHeaderTimeout: 5 * time.Second,
		ReadTimeout:       15 * time.Second,
		WriteTimeout:      15 * time.Second,
		IdleTimeout:       60 * time.Second,
		MaxHeaderBytes:    16 << 10,
	}

	healthSrv := &http.Server{
		Addr:              a.cfg.HealthAddr,
		ReadHeaderTimeout: 3 * time.Second,
		ReadTimeout:       5 * time.Second,
		WriteTimeout:      5 * time.Second,
		IdleTimeout:       30 * time.Second,
		Handler: http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			if r.URL.Path != "/healthz" {
				http.NotFound(w, r)
				return
			}
			writeJSON(w, http.StatusOK, map[string]any{
				"status":          "ok",
				"node":            a.cfg.NodeName,
				"peer_id":         a.host.ID().String(),
				"event_topic":     eventTopicName,
				"prediction_topic": predictionTopicName,
				"forward_mode": a.cfg.ForwardMode,
				"rendezvous": a.cfg.Rendezvous,
			})
		}),
	}

	errCh := make(chan error, 2)

	go func() {
		log.Printf("ingress mTLS server listening on %s", a.cfg.IngressAddr)
		if err := ingressSrv.ListenAndServeTLS("", ""); err != nil && !errors.Is(err, http.ErrServerClosed) {
			errCh <- err
		}
	}()

	go func() {
		log.Printf("health server listening on %s", a.cfg.HealthAddr)
		if err := healthSrv.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
			errCh <- err
		}
	}()

	select {
	case <-ctx.Done():
		shutdownCtx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
		defer cancel()
		_ = ingressSrv.Shutdown(shutdownCtx)
		_ = healthSrv.Shutdown(shutdownCtx)
		return nil
	case err := <-errCh:
		return err
	}
}

func (a *App) handleHealth(w http.ResponseWriter, _ *http.Request) {
	writeJSON(w, http.StatusOK, map[string]any{
		"status":  "ok",
		"peer_id": a.host.ID().String(),
	})
}

func (a *App) handleIngest(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
		return
	}

	defer r.Body.Close()
	r.Body = http.MaxBytesReader(w, r.Body, 1<<20)

	var req IngressRequest
	decoder := json.NewDecoder(r.Body)
	decoder.DisallowUnknownFields()
	if err := decoder.Decode(&req); err != nil {
		http.Error(w, "invalid json", http.StatusBadRequest)
		return
	}

	if err := validateIngress(req); err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}

	resolved, err := a.resolveAPIKey(r.Context(), req.APIKey)
	if err != nil {
		http.Error(w, "invalid API key", http.StatusUnauthorized)
		return
	}
	if a.cfg.EnforceDeviceBinding && resolved.DeviceID != "" && resolved.DeviceID != req.Event.DeviceID {
		http.Error(w, "API key is not authorized for this device", http.StatusForbidden)
		return
	}
	if a.cfg.RequireEventSignature && !verifyEventSignature(req.APIKey, req.Event) {
		http.Error(w, "invalid event signature", http.StatusUnauthorized)
		return
	}

	envelope := SwarmEnvelope{
		EnvelopeID:   randomEnvelopeID(req),
		APIKey:       req.APIKey,
		OrgID:        resolved.OrgID,
		KeyID:        resolved.KeyID,
		Event:        req.Event,
		OriginPeerID: a.host.ID().String(),
		CreatedAt:    time.Now().UTC(),
	}

	if err := a.forwardToAuthority(r.Context(), envelope); err != nil {
		log.Printf("forward error envelope_id=%s err=%v", envelope.EnvelopeID, err)
		http.Error(w, "authority unavailable", http.StatusBadGateway)
		return
	}

	data, err := json.Marshal(envelope)
	if err != nil {
		http.Error(w, "serialization failed", http.StatusInternalServerError)
		return
	}

	if err := a.eventTopic.Publish(r.Context(), data); err != nil {
		http.Error(w, "publish failed", http.StatusBadGateway)
		return
	}

	eventsIngested.Inc()
	eventsForwarded.Inc()
	writeJSON(w, http.StatusAccepted, map[string]any{
		"status":      "accepted",
		"envelope_id": envelope.EnvelopeID,
		"origin_peer": envelope.OriginPeerID,
	})
}

func (a *App) handleIngestPrediction(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
		return
	}

	defer r.Body.Close()
	r.Body = http.MaxBytesReader(w, r.Body, 1<<20)

	var req PredictionIngressRequest
	decoder := json.NewDecoder(r.Body)
	decoder.DisallowUnknownFields()
	if err := decoder.Decode(&req); err != nil {
		http.Error(w, "invalid json", http.StatusBadRequest)
		return
	}

	pred, err := predictionToEvent(req)
	if err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}

	resolved, err := a.resolveAPIKey(r.Context(), req.APIKey)
	if err != nil {
		http.Error(w, "invalid API key", http.StatusUnauthorized)
		return
	}
	if a.cfg.EnforceDeviceBinding && resolved.DeviceID != "" && resolved.DeviceID != pred.DeviceID {
		http.Error(w, "API key is not authorized for this device", http.StatusForbidden)
		return
	}
	if a.cfg.RequireEventSignature && !verifyEventSignature(req.APIKey, pred) {
		http.Error(w, "invalid event signature", http.StatusUnauthorized)
		return
	}

	envelope := SwarmEnvelope{
		EnvelopeID:   randomPredictionEnvelopeID(req),
		APIKey:       req.APIKey,
		OrgID:        resolved.OrgID,
		KeyID:        resolved.KeyID,
		Event:        pred,
		OriginPeerID: a.host.ID().String(),
		CreatedAt:    time.Now().UTC(),
	}

	if err := a.forwardToAuthority(r.Context(), envelope); err != nil {
		log.Printf("prediction forward error envelope_id=%s err=%v", envelope.EnvelopeID, err)
		http.Error(w, "authority unavailable", http.StatusBadGateway)
		return
	}

	data, err := json.Marshal(envelope)
	if err != nil {
		http.Error(w, "serialization failed", http.StatusInternalServerError)
		return
	}

	if err := a.predTopic.Publish(r.Context(), data); err != nil {
		http.Error(w, "publish failed", http.StatusBadGateway)
		return
	}

	eventsIngested.Inc()
	writeJSON(w, http.StatusAccepted, map[string]any{
		"status":      "accepted",
		"envelope_id": envelope.EnvelopeID,
		"origin_peer": envelope.OriginPeerID,
	})
}

func canonicalEvent(event EventPayload) string {
	return strings.Join(
		[]string{
			event.DeviceID,
			event.EventType,
			fmt.Sprintf("%.6f", event.Confidence),
			event.Location,
			event.FrameHash,
		},
		"\n",
	)
}

func verifyEventSignature(apiKey string, event EventPayload) bool {
	signature, err := hex.DecodeString(strings.TrimSpace(event.Signature))
	if err != nil || len(signature) != sha256.Size {
		return false
	}
	mac := hmac.New(sha256.New, []byte(apiKey))
	_, _ = mac.Write([]byte(canonicalEvent(event)))
	return hmac.Equal(signature, mac.Sum(nil))
}

func (a *App) resolveAPIKey(ctx context.Context, apiKey string) (resolvedAPIKey, error) {
	body, err := json.Marshal(map[string]string{"api_key": apiKey})
	if err != nil {
		return resolvedAPIKey{}, err
	}
	req, err := http.NewRequestWithContext(
		ctx,
		http.MethodPost,
		strings.TrimRight(a.cfg.AuthServiceURL, "/")+"/internal/api-keys/resolve",
		bytes.NewReader(body),
	)
	if err != nil {
		return resolvedAPIKey{}, err
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-Internal-Auth", a.cfg.InternalAPIKey)

	resp, err := a.httpClient.Do(req)
	if err != nil {
		return resolvedAPIKey{}, fmt.Errorf("auth service unavailable: %w", err)
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		return resolvedAPIKey{}, fmt.Errorf("auth service rejected key with status %d", resp.StatusCode)
	}

	var resolved resolvedAPIKey
	decoder := json.NewDecoder(io.LimitReader(resp.Body, 8<<10))
	if err := decoder.Decode(&resolved); err != nil {
		return resolvedAPIKey{}, fmt.Errorf("invalid auth response: %w", err)
	}
	if strings.TrimSpace(resolved.OrgID) == "" || strings.TrimSpace(resolved.KeyID) == "" {
		return resolvedAPIKey{}, errors.New("auth response is missing key context")
	}
	return resolved, nil
}

func validateIngress(req IngressRequest) error {
	if req.APIKey == "" {
		return errors.New("api_key is required")
	}
	if req.Event.DeviceID == "" {
		return errors.New("event.device_id is required")
	}
	if req.Event.EventType == "" {
		return errors.New("event.event_type is required")
	}
	if req.Event.Confidence < 0 || req.Event.Confidence > 1 {
		return errors.New("event.confidence must be between 0 and 1")
	}
	if req.Event.FrameHash != "" {
		if _, err := hex.DecodeString(req.Event.FrameHash); err != nil {
			return errors.New("event.frame_hash must be valid hex")
		}
	}
	if req.Event.Signature != "" {
		if _, err := hex.DecodeString(req.Event.Signature); err != nil {
			return errors.New("event.signature must be valid hex")
		}
	}
	return nil
}

func randomEnvelopeID(req IngressRequest) string {
	h := sha256.Sum256([]byte(fmt.Sprintf("%s|%s|%f|%d", req.APIKey, req.Event.DeviceID, req.Event.Confidence, time.Now().UnixNano())))
	return hex.EncodeToString(h[:16])
}

func randomPredictionEnvelopeID(req PredictionIngressRequest) string {
	deviceID, _ := req.Prediction["device_id"].(string)
	h := sha256.Sum256([]byte(fmt.Sprintf("%s|%s|%d", req.APIKey, deviceID, time.Now().UnixNano())))
	return hex.EncodeToString(h[:16])
}

func predictionToEvent(req PredictionIngressRequest) (EventPayload, error) {
	if req.APIKey == "" {
		return EventPayload{}, errors.New("api_key is required")
	}
	if req.Prediction == nil {
		return EventPayload{}, errors.New("prediction is required")
	}

	deviceID, _ := req.Prediction["device_id"].(string)
	eventType, _ := req.Prediction["event_type"].(string)
	location, _ := req.Prediction["location"].(string)
	frameHash, _ := req.Prediction["frame_hash"].(string)
	signature, _ := req.Prediction["signature"].(string)

	if deviceID == "" {
		return EventPayload{}, errors.New("prediction.device_id is required")
	}
	if eventType == "" {
		return EventPayload{}, errors.New("prediction.event_type is required")
	}

	confidenceRaw, ok := req.Prediction["confidence"]
	if !ok {
		return EventPayload{}, errors.New("prediction.confidence is required")
	}
	confidence, err := toFloat64(confidenceRaw)
	if err != nil {
		return EventPayload{}, errors.New("prediction.confidence must be numeric")
	}

	payload := EventPayload{
		DeviceID:   deviceID,
		EventType:  eventType,
		Confidence: confidence,
		Location:   location,
		FrameHash:  frameHash,
		Signature:  signature,
	}

	if err := validateIngress(IngressRequest{APIKey: req.APIKey, Event: payload}); err != nil {
		return EventPayload{}, err
	}

	return payload, nil
}

func toFloat64(value any) (float64, error) {
	switch v := value.(type) {
	case float64:
		return v, nil
	case float32:
		return float64(v), nil
	case int:
		return float64(v), nil
	case int64:
		return float64(v), nil
	case json.Number:
		return v.Float64()
	default:
		return 0, errors.New("invalid numeric value")
	}
}

func (a *App) forwardToAuthority(ctx context.Context, env SwarmEnvelope) error {
	switch a.cfg.ForwardMode {
	case "backend-http":
		return a.forwardToBackend(ctx, env)
	case "http", "validator-http", "validator-rest":
		return a.forwardToValidatorREST(ctx, env)
	case "validator-grpc":
		return a.forwardToValidatorGRPC(ctx, env)
	default:
		return fmt.Errorf("unsupported SWARM_FORWARD_MODE=%s", a.cfg.ForwardMode)
	}
}

func (a *App) forwardToBackend(ctx context.Context, env SwarmEnvelope) error {
	payload, err := json.Marshal(env.Event)
	if err != nil {
		return fmt.Errorf("marshal backend payload: %w", err)
	}

	req, err := http.NewRequestWithContext(ctx, http.MethodPost, a.cfg.BackendURL, bytes.NewReader(payload))
	if err != nil {
		return fmt.Errorf("create request: %w", err)
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-API-Key", env.APIKey)
	req.Header.Set("X-Swarm-Envelope-Id", env.EnvelopeID)
	req.Header.Set("X-Swarm-Origin", env.OriginPeerID)

	resp, err := a.httpClient.Do(req)
	if err != nil {
		return fmt.Errorf("backend request failed: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode >= 300 {
		body, _ := io.ReadAll(io.LimitReader(resp.Body, 1024))
		return fmt.Errorf("backend status=%d body=%s", resp.StatusCode, strings.TrimSpace(string(body)))
	}

	log.Printf("forwarded envelope_id=%s to backend status=%d", env.EnvelopeID, resp.StatusCode)
	return nil
}

func (a *App) forwardToValidatorREST(ctx context.Context, env SwarmEnvelope) error {
	payload := map[string]any{
		"creator":        a.cfg.CreatorAddress,
		"org_id":         env.OrgID,
		"key_id":         env.KeyID,
		"device_id":      env.Event.DeviceID,
		"event_type":     env.Event.EventType,
		"confidence":     uint64(env.Event.Confidence * 100),
		"confidence_f":   env.Event.Confidence,
		"frame_hash":     env.Event.FrameHash,
		"signature":      env.Event.Signature,
		"envelope_id":    env.EnvelopeID,
		"origin_peer_id": env.OriginPeerID,
		"location":       env.Event.Location,
	}

	bz, err := json.Marshal(payload)
	if err != nil {
		return fmt.Errorf("marshal validator payload: %w", err)
	}

	req, err := http.NewRequestWithContext(ctx, http.MethodPost, a.cfg.ValidatorSubmitURL, bytes.NewReader(bz))
	if err != nil {
		return fmt.Errorf("create validator request: %w", err)
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-Internal-Auth", a.cfg.InternalAPIKey)

	resp, err := a.httpClient.Do(req)
	if err != nil {
		return fmt.Errorf("validator request failed: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode >= 300 {
		body, _ := io.ReadAll(io.LimitReader(resp.Body, 1024))
		return fmt.Errorf("validator status=%d body=%s", resp.StatusCode, strings.TrimSpace(string(body)))
	}

	log.Printf("forwarded envelope_id=%s to validator status=%d", env.EnvelopeID, resp.StatusCode)
	return nil
}

type validatorSubmitRequest struct {
	Creator      string       `json:"creator"`
	OrgID        string       `json:"org_id"`
	DeviceID     string       `json:"device_id"`
	EventType    string       `json:"event_type"`
	Confidence   uint64       `json:"confidence"`
	ConfidenceF  float64      `json:"confidence_f,omitempty"`
	FrameHash    string       `json:"frame_hash,omitempty"`
	Signature    string       `json:"signature,omitempty"`
	EnvelopeID   string       `json:"envelope_id"`
	OriginPeerID string       `json:"origin_peer_id"`
	Location     string       `json:"location,omitempty"`
}

type validatorSubmitResponse struct {
	Code    int    `json:"code"`
	Height  string `json:"height"`
	TxHash  string `json:"txhash"`
	Status  string `json:"status"`
	Message string `json:"message,omitempty"`
}

type jsonCodec struct{}

func (jsonCodec) Name() string { return "json" }

func (jsonCodec) Marshal(v interface{}) ([]byte, error) {
	return json.Marshal(v)
}

func (jsonCodec) Unmarshal(data []byte, v interface{}) error {
	return json.Unmarshal(data, v)
}

func (a *App) forwardToValidatorGRPC(ctx context.Context, env SwarmEnvelope) error {
	grpcCtx, cancel := context.WithTimeout(ctx, a.cfg.ValidatorGRPCTimeout)
	defer cancel()

	encoding.RegisterCodec(jsonCodec{})

	conn, err := grpc.DialContext(
		grpcCtx,
		a.cfg.ValidatorGRPCAddr,
		grpc.WithTransportCredentials(insecure.NewCredentials()),
		grpc.WithDefaultCallOptions(grpc.ForceCodec(jsonCodec{})),
	)
	if err != nil {
		return fmt.Errorf("grpc dial failed: %w", err)
	}
	defer conn.Close()

	request := validatorSubmitRequest{
		Creator:      a.cfg.CreatorAddress,
		OrgID:        env.OrgID,
		DeviceID:     env.Event.DeviceID,
		EventType:    env.Event.EventType,
		Confidence:   uint64(env.Event.Confidence * 100),
		ConfidenceF:  env.Event.Confidence,
		FrameHash:    env.Event.FrameHash,
		Signature:    env.Event.Signature,
		EnvelopeID:   env.EnvelopeID,
		OriginPeerID: env.OriginPeerID,
		Location:     env.Event.Location,
	}

	response := validatorSubmitResponse{}
	if err := conn.Invoke(grpcCtx, "/galaxy.galaxy.Msg/SubmitEvent", request, &response, grpc.ForceCodec(jsonCodec{})); err != nil {
		return fmt.Errorf("grpc submit failed: %w", err)
	}

	if response.Code != 0 {
		return fmt.Errorf("validator rejected code=%d message=%s", response.Code, response.Message)
	}

	log.Printf("forwarded envelope_id=%s to validator grpc tx=%s", env.EnvelopeID, response.TxHash)
	return nil
}

func (a *App) serverTLSConfig() (*tls.Config, error) {
	cert, err := tls.LoadX509KeyPair(a.cfg.ServerCertPath, a.cfg.ServerKeyPath)
	if err != nil {
		return nil, fmt.Errorf("load server cert: %w", err)
	}

	caBytes, err := os.ReadFile(a.cfg.ClientCAPath)
	if err != nil {
		return nil, fmt.Errorf("read client ca: %w", err)
	}

	clientCAPool := x509.NewCertPool()
	if !clientCAPool.AppendCertsFromPEM(caBytes) {
		return nil, errors.New("append client ca failed")
	}

	return &tls.Config{
		MinVersion:               tls.VersionTLS13,
		ClientAuth:               tls.RequireAndVerifyClientCert,
		ClientCAs:                clientCAPool,
		Certificates:             []tls.Certificate{cert},
		PreferServerCipherSuites: true,
	}, nil
}

func (a *App) markSeen(id string) bool {
	a.seenMu.Lock()
	defer a.seenMu.Unlock()
	if _, exists := a.seen[id]; exists {
		return false
	}
	a.seen[id] = time.Now()
	return true
}

func (a *App) cleanupLoop(ctx context.Context) {
	ticker := time.NewTicker(30 * time.Second)
	defer ticker.Stop()
	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			deadline := time.Now().Add(-a.cfg.RedispatchTimeout)
			a.seenMu.Lock()
			for k, ts := range a.seen {
				if ts.Before(deadline) {
					delete(a.seen, k)
				}
			}
			a.seenMu.Unlock()
		}
	}
}

func (a *App) close() {
	if a.eventSub != nil {
		a.eventSub.Cancel()
	}
	if a.predSub != nil {
		a.predSub.Cancel()
	}
	if a.eventTopic != nil {
		_ = a.eventTopic.Close()
	}
	if a.predTopic != nil {
		_ = a.predTopic.Close()
	}
	if a.dht != nil {
		_ = a.dht.Close()
	}
	if a.host != nil {
		_ = a.host.Close()
	}
}

func keyFromSeed(seed string) (crypto.PrivKey, error) {
	hash := sha256.Sum256([]byte(seed))
	private := ed25519.NewKeyFromSeed(hash[:])
	return crypto.UnmarshalEd25519PrivateKey(private)
}

func peerInfoFromSeedSpec(spec string) (*peer.AddrInfo, error) {
	parts := strings.Split(spec, "@")
	if len(parts) != 2 {
		return nil, fmt.Errorf("seed spec must be seed@host:port")
	}
	seed := parts[0]
	hostPort := parts[1]
	hostName, portStr, err := net.SplitHostPort(hostPort)
	if err != nil {
		return nil, fmt.Errorf("invalid host:port: %w", err)
	}
	port, err := strconv.Atoi(portStr)
	if err != nil {
		return nil, fmt.Errorf("invalid port: %w", err)
	}

	pk, err := keyFromSeed(seed)
	if err != nil {
		return nil, err
	}
	peerID, err := peer.IDFromPrivateKey(pk)
	if err != nil {
		return nil, err
	}
	maddr, err := ma.NewMultiaddr(fmt.Sprintf("/dns4/%s/tcp/%d", hostName, port))
	if err != nil {
		return nil, err
	}

	return &peer.AddrInfo{ID: peerID, Addrs: []ma.Multiaddr{maddr}}, nil
}

func splitCSV(value string) []string {
	if strings.TrimSpace(value) == "" {
		return nil
	}
	raw := strings.Split(value, ",")
	out := make([]string, 0, len(raw))
	for _, item := range raw {
		item = strings.TrimSpace(item)
		if item != "" {
			out = append(out, item)
		}
	}
	return out
}

func envBool(key string, fallback bool) bool {
	value := strings.TrimSpace(strings.ToLower(os.Getenv(key)))
	if value == "" {
		return fallback
	}
	switch value {
	case "1", "true", "yes":
		return true
	case "0", "false", "no":
		return false
	default:
		log.Printf("invalid boolean for %s=%q, using %t", key, value, fallback)
		return fallback
	}
}

func parseIntEnv(key string, fallback int) (int, error) {
	value := strings.TrimSpace(os.Getenv(key))
	if value == "" {
		return fallback, nil
	}
	n, err := strconv.Atoi(value)
	if err != nil {
		return 0, fmt.Errorf("%s must be an integer", key)
	}
	return n, nil
}

func parseDurationEnv(key string, fallback time.Duration) time.Duration {
	value := strings.TrimSpace(os.Getenv(key))
	if value == "" {
		return fallback
	}
	d, err := time.ParseDuration(value)
	if err != nil {
		log.Printf("invalid duration for %s=%s, using %s", key, value, fallback)
		return fallback
	}
	return d
}

func envOrDefault(key, fallback string) string {
	value := strings.TrimSpace(os.Getenv(key))
	if value == "" {
		return fallback
	}
	return value
}

func writeJSON(w http.ResponseWriter, status int, payload map[string]any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(payload)
}
