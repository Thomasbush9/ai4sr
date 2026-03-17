FROM nginx:alpine

# Install wget for healthcheck and openssl for cert generation
RUN apk add --no-cache wget openssl

# Generate self-signed SSL certs if not mounted at runtime
RUN mkdir -p /etc/nginx/ssl && \
    openssl req -new -x509 -nodes \
      -keyout /etc/nginx/ssl/key.pem \
      -out /etc/nginx/ssl/cert.pem \
      -days 365 \
      -subj "/C=US/ST=State/L=City/O=AI4SR/CN=localhost" \
      -addext "subjectAltName=DNS:localhost,IP:127.0.0.1" && \
    chmod 600 /etc/nginx/ssl/key.pem && \
    chmod 644 /etc/nginx/ssl/cert.pem
