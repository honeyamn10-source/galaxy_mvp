package app

import (
	"context"

	"galaxy/authority-chain/internal/authority"
)

// GalaxyApp is the Phase III authority-chain application shell for galaxyd.
type GalaxyApp struct {
	Server *authority.Server
}

func New() (*GalaxyApp, error) {
	srv, err := authority.NewServerFromEnv()
	if err != nil {
		return nil, err
	}
	return &GalaxyApp{Server: srv}, nil
}

func (a *GalaxyApp) Start(ctx context.Context) error {
	return a.Server.Start(ctx)
}
