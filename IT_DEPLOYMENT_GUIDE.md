# IT Deployment Guide

## HTTP to HTTPS Migration

### Port Configuration Changes

**Previous Setup:**
- Flask app exposed directly on port 5001 (HTTP)

**Current Setup:**
- Flask app runs internally on port 5001 (not exposed externally)
- nginx reverse proxy handles external access
- **HTTPS:** External port `5001` → Internal port `443` (HTTPS)
- **HTTP:** External port `80` → Redirects to HTTPS (301 redirect)

**Key Changes:**
- Application now accessible via `https://localhost:5001` (not `http://localhost:5001`)
- HTTP traffic on port 80 automatically redirects to HTTPS
- SSL termination handled by nginx
- Flask app communicates with nginx over internal Docker network

**Port Mappings (docker-compose.yml):**
```yaml
nginx:
  ports:
    - "5001:443"  # HTTPS
    - "80:80"     # HTTP redirect
```

## Installation Guide

### Prerequisites
- Docker & Docker Compose
- Git
- OpenSSL (for certificate generation)

### Step 1: Clone Repository
```bash
git clone <repository-url>
cd ai4sr
```

### Step 2: Environment Configuration
```bash
cp env.example .env
```

Edit `.env` and set required variables:
```bash
OPENAI_KEY=sk-your-api-key-here
```

### Step 3: Generate SSL Certificates
```bash
chmod +x nginx/generate-certs.sh
./nginx/generate-certs.sh
```

This creates self-signed certificates in `nginx/ssl/`:
- `cert.pem` (certificate)
- `key.pem` (private key)

**Note:** For production, replace with certificates from a trusted CA (e.g., Let's Encrypt).

### Step 4: Database Setup
Database auto-initializes on first run. No manual setup required.

If manual initialization needed:
```bash
python scripts/init_db.py
```

### Step 5: Build and Start Containers
```bash
docker-compose up --build -d
```

### Step 6: Verify Deployment
```bash
# Check container status
docker-compose ps

# Test HTTPS endpoint
curl -k https://localhost:5001/api/health

# View logs
docker-compose logs -f
```

### Step 7: Access Application
Open `https://localhost:5001` in browser.

**Note:** Self-signed certificates trigger browser security warnings. Click "Advanced" → "Proceed to localhost" to continue.

## Production Considerations

### SSL Certificates
Replace self-signed certificates in `nginx/ssl/` with trusted certificates:
- Let's Encrypt (recommended): Use certbot with nginx plugin
- Custom certificates: Place `cert.pem` and `key.pem` in `nginx/ssl/`

### Environment Variables
Set production variables in `.env`:
```bash
FLASK_ENV=production
FLASK_SECRET_KEY=$(python -c "import secrets; print(secrets.token_hex(32))")
```

### Firewall Rules
Ensure ports are open:
- Port `5001` (HTTPS) - external access
- Port `80` (HTTP redirect) - optional, for redirects

## Troubleshooting

### Port Conflicts
If port 5001 is in use, update `docker-compose.yml`:
```yaml
ports:
  - "5002:443"  # Change external port
```

### Certificate Issues
Regenerate certificates:
```bash
rm -rf nginx/ssl/*
./nginx/generate-certs.sh
docker-compose restart nginx
```

### Database Issues
Reset database:
```bash
rm data/review.db
docker-compose restart ai4sr
```

## Architecture Overview

```
Internet → nginx:443 (HTTPS) → Flask:5001 (HTTP internal)
         → nginx:80 (HTTP) → Redirect 301 → HTTPS
```

**Network:**
- Containers communicate via `ai4sr_network` (bridge)
- Flask app accessible only from nginx container
- Data persisted in `./data` and `./logs` volumes

