# MCP Gateway - NGINX Configuration Documentation

**File:** `nginx-gateway.conf`  
**Copyright:** © 2025 LAB271  
**Purpose:** Routes traffic to MCP (Model Context Protocol) servers via subpaths

## Overview

This NGINX configuration acts as a **gateway/reverse proxy** for MCP servers, providing:
- **Centralized access point** for multiple MCP services
- **SSL/TLS termination** for secure communications
- **Load balancing** and health checking
- **Subpath-based routing** (e.g., `/log/` routes to log-mcp service)

## Architecture

```
Client Request (HTTPS)
        ↓
   NGINX Gateway (port 443)
        ↓
   Route by Path
        ↓
   /log/* → log-mcp:8000
   /quotes/* → quotes-mcp:8001 (future)
   /calculator/* → calculator-mcp:8002 (future)
```

## Key Components

### 1. HTTP to HTTPS Redirect (Port 80)

```nginx
server {
    listen 80;
    location / {
        return 301 https://$server_name$request_uri;
    }
}
```

- All HTTP traffic is redirected to HTTPS for security
- Exception: `/health` endpoint remains accessible on HTTP for load balancer checks

### 2. HTTPS Server (Port 443)

The main server listens on port 443 with:
- **SSL/TLS 1.2 and 1.3** support
- **HTTP/2** enabled for better performance
- Strong cipher suites (HIGH:!aNULL:!MD5)

### 3. SSL Configuration

```nginx
ssl_certificate /etc/nginx/ssl/mcp.crt;
ssl_certificate_key /etc/nginx/ssl/mcp.key;
ssl_protocols TLSv1.2 TLSv1.3;
```

Requires SSL certificates to be mounted at:
- Certificate: `/etc/nginx/ssl/mcp.crt`
- Private key: `/etc/nginx/ssl/mcp.key`

### 4. Security Headers

The configuration adds important security headers to all responses:

| Header | Purpose |
|--------|---------|
| `X-Frame-Options` | Prevents clickjacking attacks |
| `X-Content-Type-Options` | Prevents MIME-sniffing attacks |
| `X-XSS-Protection` | Enables browser XSS protection |
| `Referrer-Policy` | Controls referrer information |

### 5. Upstream Backend

```nginx
upstream log-mcp-backend {
    server log-mcp:8000 max_fails=3 fail_timeout=30s;
}
```

- **Service name:** `log-mcp` (Docker service name)
- **Port:** 8000
- **Health checking:** Max 3 failures before marking as down
- **Failure timeout:** 30 seconds before retry

## Routing Rules

### Root Endpoint (`/`)

```json
{
  "status": "ok",
  "message": "MCP Gateway",
  "version": "1.0",
  "services": [
    {
      "name": "log-mcp",
      "path": "/log/"
    }
  ]
}
```

Returns gateway information and available services.

### Health Check (`/health`)

```json
{
  "status": "healthy",
  "gateway": "nginx",
  "timestamp": "2025-10-31T13:58:28+01:00"
}
```

Gateway-level health check (not logging is disabled for this endpoint).

### Log MCP Service (`/log/*`)

Routes all requests starting with `/log/` to the log-mcp backend:

```nginx
location /log/ {
    rewrite ^/log/(.*)$ /$1 break;
    proxy_pass http://log-mcp-backend;
}
```

**Path rewriting example:**
- Client requests: `https://mcp.local/log/api/logs`
- NGINX forwards to: `http://log-mcp:8000/api/logs`

The `/log` prefix is stripped before forwarding.

### Service Health Check (`/log/health`)

Direct health check for the log-mcp service:
- Forwards to: `http://log-mcp:8000/health`
- Access logging disabled for performance

## Proxy Configuration

### Headers Set by Gateway

The gateway adds/modifies these headers when forwarding:

| Header | Value | Purpose |
|--------|-------|---------|
| `Host` | Original host | Preserve original hostname |
| `X-Real-IP` | Client IP | Original client IP |
| `X-Forwarded-For` | Client IP chain | Track proxy chain |
| `X-Forwarded-Proto` | `https` | Original protocol |
| `X-Forwarded-Host` | Original host | Original hostname |
| `X-Forwarded-Port` | `443` | Original port |

### Timeouts

```nginx
proxy_connect_timeout 60s;      # Connection establishment
proxy_send_timeout 60s;         # Sending request
proxy_read_timeout 300s;        # Reading response (5 minutes)
```

- **Long read timeout (300s):** Supports streaming log responses
- Connection and send timeouts are shorter (60s)

### Buffering

```nginx
proxy_buffering off;
proxy_request_buffering off;
```

- **Disabled buffering:** Critical for streaming responses
- Enables real-time log streaming without waiting for complete response

### WebSocket Support

```nginx
proxy_set_header Upgrade $http_upgrade;
proxy_set_header Connection "upgrade";
```

Enables WebSocket connections if MCP services need bidirectional communication.

### Error Handling

```nginx
proxy_next_upstream error timeout invalid_header http_500 http_502 http_503;
proxy_next_upstream_tries 2;
```

Automatically retries failed requests up to 2 times on:
- Connection errors
- Timeouts
- Invalid headers
- 5xx server errors

## Performance Features

### Gzip Compression

```nginx
gzip on;
gzip_min_length 1024;
gzip_types text/plain text/css application/json ...;
```

Compresses responses larger than 1KB for supported content types.

### Connection Settings

```nginx
worker_processes auto;          # One per CPU core
worker_connections 1024;        # Max connections per worker
keepalive_timeout 65;           # Keep connections alive
```

## Adding New MCP Services

To add a new MCP service (e.g., quotes-mcp):

1. **Define upstream:**
```nginx
upstream quotes-mcp-backend {
    server quotes-mcp:8001 max_fails=3 fail_timeout=30s;
}
```

2. **Add location block:**
```nginx
location /quotes/ {
    rewrite ^/quotes/(.*)$ /$1 break;
    proxy_pass http://quotes-mcp-backend;
    # ... copy proxy settings from /log/ ...
}
```

3. **Update root endpoint response** to include new service in the services array.

## Logging

### Access Log Format

```
$remote_addr - $remote_user [$time_local] "$request" 
$status $body_bytes_sent "$http_referer" 
"$http_user_agent" "upstream: $upstream_addr"
```

Includes the upstream backend that handled the request.

### Log Locations

**Container logs:**
- **Access log:** `/var/log/nginx/access.log`
- **Error log:** `/var/log/nginx/error.log`

**Host system logs (mounted):**
- **Host directory:** `/tmp/log/nginx/` (on macOS)
- **Access log:** `/tmp/log/nginx/access.log`
- **Error log:** `/tmp/log/nginx/error.log`

The logs are forwarded to the host system via Docker volume mount for easy access and monitoring.

Health check endpoints have access logging disabled.

## Security Considerations

1. **TLS Only:** All traffic redirected to HTTPS
2. **Modern Protocols:** TLS 1.2 and 1.3 only
3. **Strong Ciphers:** HIGH strength ciphers, MD5 disabled
4. **Security Headers:** Protection against common attacks
5. **Upstream Isolation:** Backend services not directly exposed

## Docker Integration

This configuration is designed to run in Docker with:
- Service discovery via Docker DNS (e.g., `log-mcp` hostname)
- Volume-mounted SSL certificates
- Shared Docker network with MCP services

## Troubleshooting

### Check Gateway Status
```bash
curl https://mcp.local/health
```

### Check Service Status
```bash
curl https://mcp.local/log/health
```

### View Logs
```bash
docker compose logs nginx-gateway
```

### Test SSL Configuration
```bash
openssl s_client -connect mcp.local:443 -showcerts
```

## Future Enhancements

The configuration includes placeholder comments for future MCP services:
```nginx
# Future MCP servers can be added here with similar patterns:
# location /quotes/ { ... }
# location /calculator/ { ... }
```

This allows easy expansion of the gateway to route to additional MCP services.
