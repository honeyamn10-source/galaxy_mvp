FROM golang:1.22-alpine AS builder

WORKDIR /app
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -o authority-chain .

FROM alpine:3.20
RUN adduser -D -u 10001 chain && apk add --no-cache curl
COPY --from=builder /app/authority-chain /usr/local/bin/
USER chain
EXPOSE 9090 1317 26657
CMD ["authority-chain"]
