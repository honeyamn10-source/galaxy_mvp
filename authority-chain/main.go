package main

import (
    "encoding/json"
    "log"
    "net"
    "net/http"
    "sync"
    "time"

    "github.com/gorilla/websocket"
    "google.golang.org/grpc"
)

type Event struct {
    ID         string   `json:"id"`
    DeviceID   string   `json:"device_id"`
    EventType  string   `json:"event_type"`
    Confidence float64  `json:"confidence"`
    FrameHash  string   `json:"frame_hash"`
    Signature  string   `json:"signature"`
    Status     string   `json:"status"`
    Timestamp  int64    `json:"timestamp"`
}

var (
    events     = make(map[string]Event)
    eventsLock sync.RWMutex
    wsUpgrader = websocket.Upgrader{
        CheckOrigin: func(r *http.Request) bool { return true },
    }
    wsClients = make(map[*websocket.Conn]bool)
)

func main() {
    // Start gRPC server
    go startGRPCServer()

    // Start HTTP server
    startHTTPServer()
}

func startGRPCServer() {
    lis, err := net.Listen("tcp", ":9090")
    if err != nil {
        log.Fatalf("failed to listen: %v", err)
    }
    s := grpc.NewServer()
    // Register our dummy service (no actual protobuf, just a placeholder)
    log.Println("gRPC server listening on :9090")
    if err := s.Serve(lis); err != nil {
        log.Fatalf("failed to serve: %v", err)
    }
}

func startHTTPServer() {
    http.HandleFunc("/health", healthHandler)
    http.HandleFunc("/galaxy/v1/events", eventsHandler)
    http.HandleFunc("/cosmos/tx/v1beta1/txs", cosmosTxsHandler)
    http.HandleFunc("/ws", wsHandler)

    log.Println("HTTP server listening on :1317")
    log.Fatal(http.ListenAndServe(":1317", nil))
}

func healthHandler(w http.ResponseWriter, r *http.Request) {
    w.Header().Set("Content-Type", "application/json")
    json.NewEncoder(w).Encode(map[string]string{"status": "ok"})
}

func eventsHandler(w http.ResponseWriter, r *http.Request) {
    switch r.Method {
    case http.MethodGet:
        eventsLock.RLock()
        defer eventsLock.RUnlock()
        list := make([]Event, 0, len(events))
        for _, ev := range events {
            list = append(list, ev)
        }
        json.NewEncoder(w).Encode(map[string]interface{}{"events": list})
    case http.MethodPost:
        var ev Event
        if err := json.NewDecoder(r.Body).Decode(&ev); err != nil {
            http.Error(w, err.Error(), http.StatusBadRequest)
            return
        }
        ev.ID = r.Header.Get("X-Envelope-ID")
        if ev.ID == "" {
            ev.ID = time.Now().String()
        }
        ev.Timestamp = time.Now().Unix()
        ev.Status = "pending"
        // If LLM verdict is passed, we can store it; here just store raw
        eventsLock.Lock()
        events[ev.ID] = ev
        eventsLock.Unlock()

        // Broadcast via WebSocket
        broadcastEvent(ev)

        w.WriteHeader(http.StatusCreated)
        json.NewEncoder(w).Encode(ev)
    }
}

func cosmosTxsHandler(w http.ResponseWriter, r *http.Request) {
    // Simulate Cosmos REST endpoint for compatibility with dashboard
    w.Header().Set("Content-Type", "application/json")
    json.NewEncoder(w).Encode(map[string]interface{}{
        "txs": []interface{}{},
    })
}

func wsHandler(w http.ResponseWriter, r *http.Request) {
    conn, err := wsUpgrader.Upgrade(w, r, nil)
    if err != nil {
        log.Println("WebSocket upgrade error:", err)
        return
    }
    defer conn.Close()

    wsClients[conn] = true
    defer delete(wsClients, conn)

    for {
        // keep connection alive, read any messages
        if _, _, err := conn.ReadMessage(); err != nil {
            break
        }
    }
}

func broadcastEvent(ev Event) {
    data, _ := json.Marshal(ev)
    for conn := range wsClients {
        if err := conn.WriteMessage(websocket.TextMessage, data); err != nil {
            conn.Close()
            delete(wsClients, conn)
        }
    }
}
