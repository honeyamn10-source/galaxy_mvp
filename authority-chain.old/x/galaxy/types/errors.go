package types

import errorsmod "cosmossdk.io/errors"

const (
	CodeInvalidDevice       uint32 = 1001
	CodeInvalidFrameHash    uint32 = 1002
	CodeInvalidSignature    uint32 = 1003
	CodeEventExists         uint32 = 1004
	CodeEventNotFound       uint32 = 1005
	CodePlanetNotRegistered uint32 = 1006
	CodeNotValidator        uint32 = 1007
	CodeVotingClosed        uint32 = 1008
	CodeAlreadyVoted        uint32 = 1009
)

var (
	ErrInvalidDevice       = errorsmod.Register(ModuleName, CodeInvalidDevice, "invalid device")
	ErrInvalidFrameHash    = errorsmod.Register(ModuleName, CodeInvalidFrameHash, "invalid frame hash")
	ErrInvalidSignature    = errorsmod.Register(ModuleName, CodeInvalidSignature, "invalid signature")
	ErrEventExists         = errorsmod.Register(ModuleName, CodeEventExists, "event already exists")
	ErrEventNotFound       = errorsmod.Register(ModuleName, CodeEventNotFound, "event not found")
	ErrPlanetNotRegistered = errorsmod.Register(ModuleName, CodePlanetNotRegistered, "planet not registered")
	ErrNotValidator        = errorsmod.Register(ModuleName, CodeNotValidator, "not an active validator")
	ErrVotingClosed        = errorsmod.Register(ModuleName, CodeVotingClosed, "voting is closed")
	ErrAlreadyVoted        = errorsmod.Register(ModuleName, CodeAlreadyVoted, "validator already voted")
)
