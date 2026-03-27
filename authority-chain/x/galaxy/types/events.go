package types

type EventStatus string

const (
	StatusPending  EventStatus = "pending"
	StatusVerified EventStatus = "verified"
	StatusRejected EventStatus = "rejected"
)

type VoteType byte

const (
	VoteYes VoteType = 1
	VoteNo  VoteType = 2
)

type Planet struct {
	DeviceID  string `json:"device_id"`
	Address   string `json:"address"`
	PublicKey []byte `json:"public_key"`
}

type Event struct {
	FrameHash  []byte      `json:"frame_hash"`
	DeviceID   string      `json:"device_id"`
	EventType  string      `json:"event_type"`
	Confidence uint64      `json:"confidence"`
	Status     EventStatus `json:"status"`
	Submitter  string      `json:"submitter"`
	VotesYes   uint64      `json:"votes_yes"`
	VotesNo    uint64      `json:"votes_no"`
	VotingEnd  int64       `json:"voting_end"`
}

const (
	EventTypeSubmit   = "galaxy_submit"
	EventTypeVote     = "galaxy_vote"
	EventTypeVerified = "galaxy_verified"

	AttributeFrameHash = "frame_hash"
	AttributeDeviceID  = "device_id"
	AttributeValidator = "validator"
)
