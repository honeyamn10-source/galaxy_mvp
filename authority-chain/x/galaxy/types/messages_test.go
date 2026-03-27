package types

import (
	"testing"

	sdk "github.com/cosmos/cosmos-sdk/types"
	"github.com/cosmos/cosmos-sdk/types/address"
)

func randomAccAddress() string {
	bz := address.Module("galaxy-test", []byte("submitter"))
	return sdk.AccAddress(bz).String()
}

func randomValAddress() string {
	bz := address.Module("galaxy-test", []byte("validator"))
	return sdk.ValAddress(bz).String()
}

func TestMsgSubmitEventValidateBasic(t *testing.T) {
	msg := MsgSubmitEvent{
		Creator:    randomAccAddress(),
		DeviceID:   "planet-1",
		EventType:  "fire",
		Confidence: 91,
		FrameHash:  []byte("framehash"),
		Signature:  []byte("sig"),
	}

	if err := msg.ValidateBasic(); err != nil {
		t.Fatalf("expected valid message, got error: %v", err)
	}

	msg.DeviceID = ""
	if err := msg.ValidateBasic(); err == nil {
		t.Fatalf("expected error for missing device id")
	}
}

func TestMsgVoteEventValidateBasic(t *testing.T) {
	msg := MsgVoteEvent{
		Validator: randomValAddress(),
		FrameHash: []byte("framehash"),
		Vote:      VoteYes,
	}

	if err := msg.ValidateBasic(); err != nil {
		t.Fatalf("expected valid vote message, got error: %v", err)
	}

	msg.Vote = 9
	if err := msg.ValidateBasic(); err == nil {
		t.Fatalf("expected error for invalid vote")
	}
}
