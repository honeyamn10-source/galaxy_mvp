FROM golang:1.22-alpine AS builder

WORKDIR /src
COPY go.mod ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -o /out/galaxyd ./cmd/galaxyd

FROM alpine:3.20
RUN adduser -D -u 10001 chain && apk add --no-cache ca-certificates wget
USER chain
WORKDIR /chain

ENV CHAIN_ID=galaxy-1
ENV CHAIN_DATA_DIR=/data
ENV CHAIN_REST_ADDR=0.0.0.0:1317
ENV CHAIN_GRPC_ADDR=0.0.0.0:9090
ENV CHAIN_RPC_ADDR=0.0.0.0:26657

VOLUME ["/data"]
EXPOSE 1317 9090 26657

COPY --from=builder /out/galaxyd /chain/galaxyd
ENTRYPOINT ["/chain/galaxyd"]
