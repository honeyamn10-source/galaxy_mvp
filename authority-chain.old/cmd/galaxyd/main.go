package main

import (
	"context"
	"log"
	"os/signal"
	"syscall"

	"galaxy/authority-chain/app"
)

func main() {
	ctx, cancel := signal.NotifyContext(context.Background(), syscall.SIGINT, syscall.SIGTERM)
	defer cancel()

	galaxyApp, err := app.New()
	if err != nil {
		log.Fatalf("galaxyd init failed: %v", err)
	}

	if err := galaxyApp.Start(ctx); err != nil {
		log.Fatalf("galaxyd exited with error: %v", err)
	}
}
