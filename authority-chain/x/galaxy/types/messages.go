package types

import (
	sdkerrors "cosmossdk.io/errors"
	sdk "github.com/cosmos/cosmos-sdk/types"
)

type MsgSubmitEvent struct {
	Creator    string `json:"creator"`
	DeviceID   string `json:"device_id"`
	EventType  string `json:"event_type"`
	Confidence uint64 `json:"confidence"`
	FrameHash  []byte `json:"frame_hash"`
	Signature  []byte `json:"signature"`
}

func (msg MsgSubmitEvent) Route() string { return RouterKey }
func (msg MsgSubmitEvent) Type() string  { return "submit_event" }

func (msg MsgSubmitEvent) ValidateBasic() error {
	if _, err := sdk.AccAddressFromBech32(msg.Creator); err != nil {
		return sdkerrors.Wrap(sdkerrors.ErrInvalidAddress, "creator cannot be empty")
	}
	if msg.DeviceID == "" {
		return sdkerrors.Wrap(ErrInvalidDevice, "device id required")
	}
	if len(msg.FrameHash) == 0 {
		return sdkerrors.Wrap(ErrInvalidFrameHash, "frame hash required")
	}
	if len(msg.Signature) == 0 {
		return sdkerrors.Wrap(ErrInvalidSignature, "signature required")
	}
	if msg.Confidence > 100 {
		return sdkerrors.Wrap(sdkerrors.ErrInvalidRequest, "confidence must be <= 100")
	}
	return nil
}

func (msg MsgSubmitEvent) GetSignBytes() []byte {
	bz := ModuleCdc.MustMarshalJSON(&msg)
	return sdk.MustSortJSON(bz)
}

func (msg MsgSubmitEvent) GetSigners() []sdk.AccAddress {
	creator, _ := sdk.AccAddressFromBech32(msg.Creator)
	return []sdk.AccAddress{creator}
}

type MsgVoteEvent struct {
	Validator string   `json:"validator"`
	FrameHash []byte   `json:"frame_hash"`
	Vote      VoteType `json:"vote"`
}

func (msg MsgVoteEvent) Route() string { return RouterKey }
func (msg MsgVoteEvent) Type() string  { return "vote_event" }

func (msg MsgVoteEvent) ValidateBasic() error {
	if _, err := sdk.ValAddressFromBech32(msg.Validator); err != nil {
		return sdkerrors.Wrap(sdkerrors.ErrInvalidAddress, "validator address required")
	}
	if len(msg.FrameHash) == 0 {
		return sdkerrors.Wrap(ErrInvalidFrameHash, "frame hash required")
	}
	if msg.Vote != VoteYes && msg.Vote != VoteNo {
		return sdkerrors.Wrap(sdkerrors.ErrInvalidRequest, "invalid vote value")
	}
	return nil
}

func (msg MsgVoteEvent) GetSignBytes() []byte {
	bz := ModuleCdc.MustMarshalJSON(&msg)
	return sdk.MustSortJSON(bz)
}

func (msg MsgVoteEvent) GetSigners() []sdk.AccAddress {
	valAddr, _ := sdk.ValAddressFromBech32(msg.Validator)
	return []sdk.AccAddress{sdk.AccAddress(valAddr)}
}
