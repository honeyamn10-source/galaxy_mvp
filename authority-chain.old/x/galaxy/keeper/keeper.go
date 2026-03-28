package keeper

import (
	"crypto/ecdsa"
	"crypto/sha256"
	"crypto/x509"
	"encoding/hex"
	"fmt"

	"github.com/cosmos/cosmos-sdk/codec"
	sdk "github.com/cosmos/cosmos-sdk/types"
	"cosmossdk.io/store/prefix"

	"galaxy/authority-chain/x/galaxy/types"
)

type BankKeeper interface {
	SendCoinsFromModuleToAccount(ctx sdk.Context, senderModule string, recipientAddr sdk.AccAddress, amt sdk.Coins) error
}

type StakingKeeper interface {
	Validator(ctx sdk.Context, addr sdk.ValAddress) (sdk.ValidatorI, error)
}

type Keeper struct {
	storeKey      sdk.StoreKey
	cdc           codec.BinaryCodec
	bankKeeper    BankKeeper
	stakingKeeper StakingKeeper
	rewardModule  string
	minVotes      uint64
	votingWindow  int64
}

func NewKeeper(cdc codec.BinaryCodec, key sdk.StoreKey, bankKeeper BankKeeper, stakingKeeper StakingKeeper, rewardModule string, minVotes uint64, votingWindow int64) Keeper {
	return Keeper{
		storeKey:      key,
		cdc:           cdc,
		bankKeeper:    bankKeeper,
		stakingKeeper: stakingKeeper,
		rewardModule:  rewardModule,
		minVotes:      minVotes,
		votingWindow:  votingWindow,
	}
}

func (k Keeper) SubmitEvent(ctx sdk.Context, msg *types.MsgSubmitEvent) error {
	planet, found := k.GetPlanet(ctx, msg.DeviceID)
	if !found {
		return types.ErrPlanetNotRegistered
	}

	pubKey, err := decodePlanetKey(planet.PublicKey)
	if err != nil {
		return fmt.Errorf("decode planet key: %w", err)
	}

	hash := sha256.Sum256(msg.FrameHash)
	if !ecdsa.VerifyASN1(pubKey, hash[:], msg.Signature) {
		return types.ErrInvalidSignature
	}

	if k.HasEvent(ctx, msg.FrameHash) {
		return types.ErrEventExists
	}

	event := types.Event{
		FrameHash:  msg.FrameHash,
		DeviceID:   msg.DeviceID,
		EventType:  msg.EventType,
		Confidence: msg.Confidence,
		Status:     types.StatusPending,
		Submitter:  msg.Creator,
		VotesYes:   0,
		VotesNo:    0,
		VotingEnd:  ctx.BlockTime().Unix() + k.votingWindow,
	}
	k.SetEvent(ctx, event)

	ctx.EventManager().EmitEvent(
		sdk.NewEvent(
			types.EventTypeSubmit,
			sdk.NewAttribute(types.AttributeFrameHash, hex.EncodeToString(msg.FrameHash)),
			sdk.NewAttribute(types.AttributeDeviceID, msg.DeviceID),
		),
	)
	return nil
}

func (k Keeper) VoteEvent(ctx sdk.Context, msg *types.MsgVoteEvent) error {
	valAddr, err := sdk.ValAddressFromBech32(msg.Validator)
	if err != nil {
		return err
	}

	validator, err := k.stakingKeeper.Validator(ctx, valAddr)
	if err != nil || validator == nil || !validator.IsBonded() {
		return types.ErrNotValidator
	}

	event, found := k.GetEvent(ctx, msg.FrameHash)
	if !found {
		return types.ErrEventNotFound
	}
	if ctx.BlockTime().Unix() > event.VotingEnd {
		return types.ErrVotingClosed
	}

	voteKey := types.VoteKey(msg.FrameHash, msg.Validator)
	if k.HasVote(ctx, voteKey) {
		return types.ErrAlreadyVoted
	}

	if msg.Vote == types.VoteYes {
		event.VotesYes++
	} else {
		event.VotesNo++
	}

	k.SetEvent(ctx, event)
	k.SetVote(ctx, voteKey, byte(msg.Vote))

	ctx.EventManager().EmitEvent(
		sdk.NewEvent(
			types.EventTypeVote,
			sdk.NewAttribute(types.AttributeFrameHash, hex.EncodeToString(msg.FrameHash)),
			sdk.NewAttribute(types.AttributeValidator, msg.Validator),
		),
	)
	return nil
}

func (k Keeper) EndBlocker(ctx sdk.Context) {
	for _, event := range k.GetPendingEvents(ctx) {
		if ctx.BlockTime().Unix() < event.VotingEnd {
			continue
		}

		if event.VotesYes > event.VotesNo && event.VotesYes >= k.minVotes {
			event.Status = types.StatusVerified
			submitter, err := sdk.AccAddressFromBech32(event.Submitter)
			if err == nil {
				reward := sdk.NewCoins(sdk.NewInt64Coin("ugalaxy", 100))
				_ = k.bankKeeper.SendCoinsFromModuleToAccount(ctx, k.rewardModule, submitter, reward)
			}
			ctx.EventManager().EmitEvent(
				sdk.NewEvent(
					types.EventTypeVerified,
					sdk.NewAttribute(types.AttributeFrameHash, hex.EncodeToString(event.FrameHash)),
				),
			)
		} else {
			event.Status = types.StatusRejected
		}
		k.SetEvent(ctx, event)
	}
}

func (k Keeper) SetEvent(ctx sdk.Context, event types.Event) {
	store := prefix.NewStore(ctx.KVStore(k.storeKey), types.EventPrefix)
	bz := k.cdc.MustMarshal(&event)
	store.Set(event.FrameHash, bz)
}

func (k Keeper) GetEvent(ctx sdk.Context, frameHash []byte) (types.Event, bool) {
	store := prefix.NewStore(ctx.KVStore(k.storeKey), types.EventPrefix)
	bz := store.Get(frameHash)
	if bz == nil {
		return types.Event{}, false
	}
	var event types.Event
	k.cdc.MustUnmarshal(bz, &event)
	return event, true
}

func (k Keeper) HasEvent(ctx sdk.Context, frameHash []byte) bool {
	store := prefix.NewStore(ctx.KVStore(k.storeKey), types.EventPrefix)
	return store.Has(frameHash)
}

func (k Keeper) GetPendingEvents(ctx sdk.Context) []types.Event {
	store := prefix.NewStore(ctx.KVStore(k.storeKey), types.EventPrefix)
	iter := store.Iterator(nil, nil)
	defer iter.Close()

	out := make([]types.Event, 0)
	for ; iter.Valid(); iter.Next() {
		var event types.Event
		k.cdc.MustUnmarshal(iter.Value(), &event)
		if event.Status == types.StatusPending {
			out = append(out, event)
		}
	}
	return out
}

func (k Keeper) SetPlanet(ctx sdk.Context, planet types.Planet) {
	store := prefix.NewStore(ctx.KVStore(k.storeKey), types.PlanetPrefix)
	bz := k.cdc.MustMarshal(&planet)
	store.Set([]byte(planet.DeviceID), bz)
}

func (k Keeper) GetPlanet(ctx sdk.Context, deviceID string) (types.Planet, bool) {
	store := prefix.NewStore(ctx.KVStore(k.storeKey), types.PlanetPrefix)
	bz := store.Get([]byte(deviceID))
	if bz == nil {
		return types.Planet{}, false
	}
	var planet types.Planet
	k.cdc.MustUnmarshal(bz, &planet)
	return planet, true
}

func (k Keeper) HasVote(ctx sdk.Context, key []byte) bool {
	store := prefix.NewStore(ctx.KVStore(k.storeKey), types.VotePrefix)
	return store.Has(key)
}

func (k Keeper) SetVote(ctx sdk.Context, key []byte, vote byte) {
	store := prefix.NewStore(ctx.KVStore(k.storeKey), types.VotePrefix)
	store.Set(key, []byte{vote})
}

func decodePlanetKey(raw []byte) (*ecdsa.PublicKey, error) {
	pub, err := x509.ParsePKIXPublicKey(raw)
	if err != nil {
		return nil, err
	}
	ecdsaPub, ok := pub.(*ecdsa.PublicKey)
	if !ok {
		return nil, fmt.Errorf("planet public key is not ECDSA")
	}
	return ecdsaPub, nil
}
