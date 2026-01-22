#!/bin/bash
# Generate self-signed SSL certificates for nginx

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SSL_DIR="${SCRIPT_DIR}/ssl"

# Create ssl directory if it doesn't exist
mkdir -p "${SSL_DIR}"

# Generate private key
echo "Generating private key..."
openssl genrsa -out "${SSL_DIR}/key.pem" 2048

# Generate certificate signing request and self-signed certificate
echo "Generating self-signed certificate..."
openssl req -new -x509 -key "${SSL_DIR}/key.pem" -out "${SSL_DIR}/cert.pem" -days 365 \
    -subj "/C=US/ST=State/L=City/O=Organization/CN=localhost" \
    -addext "subjectAltName=DNS:localhost,DNS:*.localhost,IP:127.0.0.1,IP:0.0.0.0"

# Set appropriate permissions
chmod 600 "${SSL_DIR}/key.pem"
chmod 644 "${SSL_DIR}/cert.pem"

echo "✓ SSL certificates generated successfully!"
echo "  Certificate: ${SSL_DIR}/cert.pem"
echo "  Private key: ${SSL_DIR}/key.pem"
echo ""
echo "Note: These are self-signed certificates. Browsers will show a security warning."
echo "For production, replace with certificates from a trusted CA (e.g., Let's Encrypt)."

