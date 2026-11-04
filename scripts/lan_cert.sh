#!/usr/bin/env bash
# Self-signed HTTPS cert for testing on a phone/iPad over the local Wi-Fi (mic needs HTTPS).
# Local use only: certs/ is git-ignored. The phone will show a warning you accept once.
set -euo pipefail
IP="${1:-$(ipconfig getifaddr en0 2>/dev/null || hostname -I | awk '{print $1}')}"
mkdir -p certs
openssl req -x509 -newkey rsa:2048 -nodes -days 14 -keyout certs/lan-key.pem -out certs/lan-cert.pem \
  -subj "/CN=Medero dev" -addext "subjectAltName=IP:${IP},DNS:localhost,IP:127.0.0.1" 2>/dev/null
echo "$IP" > certs/ip.txt
echo "Cert for ${IP} written to certs/"
