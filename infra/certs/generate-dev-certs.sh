#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT_DIR="${ROOT_DIR}/dev"

mkdir -p "${OUT_DIR}"

CA_KEY="${OUT_DIR}/ca.key"
CA_CRT="${OUT_DIR}/ca.crt"

SWARM_KEY="${OUT_DIR}/swarm-node.key"
SWARM_CSR="${OUT_DIR}/swarm-node.csr"
SWARM_CRT="${OUT_DIR}/swarm-node.crt"

EDGE_KEY="${OUT_DIR}/edge-planet.key"
EDGE_CSR="${OUT_DIR}/edge-planet.csr"
EDGE_CRT="${OUT_DIR}/edge-planet.crt"

if [[ ! -f "${CA_KEY}" || ! -f "${CA_CRT}" ]]; then
  openssl genrsa -out "${CA_KEY}" 4096
  openssl req -x509 -new -nodes -key "${CA_KEY}" -sha256 -days 3650 \
    -subj "/CN=Galaxy Dev CA" \
    -out "${CA_CRT}"
fi

openssl genrsa -out "${SWARM_KEY}" 2048
openssl req -new -key "${SWARM_KEY}" -out "${SWARM_CSR}" \
  -subj "/CN=swarm-node"
cat > "${OUT_DIR}/swarm-node.ext" <<EOF
subjectAltName=DNS:swarm-node-1,DNS:swarm-node-2,DNS:localhost,IP:127.0.0.1
extendedKeyUsage=serverAuth,clientAuth
EOF
openssl x509 -req -in "${SWARM_CSR}" -CA "${CA_CRT}" -CAkey "${CA_KEY}" -CAcreateserial \
  -out "${SWARM_CRT}" -days 825 -sha256 -extfile "${OUT_DIR}/swarm-node.ext"

openssl genrsa -out "${EDGE_KEY}" 2048
openssl req -new -key "${EDGE_KEY}" -out "${EDGE_CSR}" \
  -subj "/CN=edge-planet"
cat > "${OUT_DIR}/edge-planet.ext" <<EOF
subjectAltName=DNS:edge-planet,DNS:localhost,IP:127.0.0.1
extendedKeyUsage=clientAuth,serverAuth
EOF
openssl x509 -req -in "${EDGE_CSR}" -CA "${CA_CRT}" -CAkey "${CA_KEY}" -CAcreateserial \
  -out "${EDGE_CRT}" -days 825 -sha256 -extfile "${OUT_DIR}/edge-planet.ext"

rm -f "${SWARM_CSR}" "${EDGE_CSR}" "${OUT_DIR}/swarm-node.ext" "${OUT_DIR}/edge-planet.ext"

echo "Generated certificates in ${OUT_DIR}"
