package keeper

import (
	"context"

	sdk "github.com/cosmos/cosmos-sdk/types"
	"github.com/cosmos/cosmos-sdk/types/errors"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"

	"galaxy/authority-chain/x/galaxy/types"
)

type msgServer struct {
	Keeper
}

func NewMsgServerImpl(k Keeper) types.MsgServer {
	return &msgServer{Keeper: k}
}

func (m msgServer) SubmitEvent(goCtx context.Context, msg *types.MsgSubmitEvent) (*types.MsgSubmitEventResponse, error) {
	ctx := sdk.UnwrapSDKContext(goCtx)
	if msg == nil {
		return nil, status.Error(codes.InvalidArgument, "empty message")
	}
	if err := msg.ValidateBasic(); err != nil {
		return nil, err
	}
	if err := m.Keeper.SubmitEvent(ctx, msg); err != nil {
		return nil, status.Error(codes.InvalidArgument, err.Error())
	}
	return &types.MsgSubmitEventResponse{}, nil
}

func (m msgServer) VoteEvent(goCtx context.Context, msg *types.MsgVoteEvent) (*types.MsgVoteEventResponse, error) {
	ctx := sdk.UnwrapSDKContext(goCtx)
	if msg == nil {
		return nil, status.Error(codes.InvalidArgument, "empty message")
	}
	if err := msg.ValidateBasic(); err != nil {
		return nil, err
	}
	if err := m.Keeper.VoteEvent(ctx, msg); err != nil {
		if errors.ErrUnauthorized.Is(err) {
			return nil, status.Error(codes.PermissionDenied, err.Error())
		}
		return nil, status.Error(codes.InvalidArgument, err.Error())
	}
	return &types.MsgVoteEventResponse{}, nil
}
