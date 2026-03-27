package types

const (
	ModuleName = "galaxy"
	StoreKey   = ModuleName
	RouterKey  = ModuleName
)

var (
	EventPrefix  = []byte{0x01}
	PlanetPrefix = []byte{0x02}
	VotePrefix   = []byte{0x03}
)

func EventKey(frameHash []byte) []byte {
	key := make([]byte, 0, len(EventPrefix)+len(frameHash))
	key = append(key, EventPrefix...)
	key = append(key, frameHash...)
	return key
}

func PlanetKey(deviceID string) []byte {
	key := make([]byte, 0, len(PlanetPrefix)+len(deviceID))
	key = append(key, PlanetPrefix...)
	key = append(key, []byte(deviceID)...)
	return key
}

func VoteKey(frameHash []byte, validator string) []byte {
	key := make([]byte, 0, len(VotePrefix)+len(frameHash)+len(validator))
	key = append(key, VotePrefix...)
	key = append(key, frameHash...)
	key = append(key, []byte(validator)...)
	return key
}
