package types

import (
	"context"

	"google.golang.org/grpc"
)

type MsgServer interface {
	SubmitEvent(context.Context, *MsgSubmitEvent) (*MsgSubmitEventResponse, error)
	VoteEvent(context.Context, *MsgVoteEvent) (*MsgVoteEventResponse, error)
}

type MsgSubmitEventResponse struct{}

type MsgVoteEventResponse struct{}

func RegisterMsgServer(s grpc.ServiceRegistrar, srv MsgServer) {
	s.RegisterService(&grpc.ServiceDesc{
		ServiceName: "galaxy.galaxy.Msg",
		HandlerType: (*MsgServer)(nil),
		Methods: []grpc.MethodDesc{
			{
				MethodName: "SubmitEvent",
				Handler: func(_ interface{}, ctx context.Context, dec func(interface{}) error, _ grpc.UnaryServerInterceptor) (interface{}, error) {
					in := new(MsgSubmitEvent)
					if err := dec(in); err != nil {
						return nil, err
					}
					return srv.SubmitEvent(ctx, in)
				},
			},
			{
				MethodName: "VoteEvent",
				Handler: func(_ interface{}, ctx context.Context, dec func(interface{}) error, _ grpc.UnaryServerInterceptor) (interface{}, error) {
					in := new(MsgVoteEvent)
					if err := dec(in); err != nil {
						return nil, err
					}
					return srv.VoteEvent(ctx, in)
				},
			},
		},
	}, srv)
}
