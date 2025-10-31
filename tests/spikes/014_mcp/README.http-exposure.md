# Exposing MCP Server over HTTP through NGINX

This guide explains how to expose a Model Context Protocol (MCP) server over HTTP through NGINX for web access.

## 🏗️ **Architecture Overview**

```
Client (Browser/curl) 
    ↓ HTTPS
NGINX Gateway (443) 
    ↓ HTTP (Internal Docker Network)
MCP Server Container (8001)
    ↓ HTTP Server + MCP Protocol Support
FastMCP Server + Custom HTTP Handler
```

## 🔧 **Implementation Methods**

### **Method 1: Dual Protocol Support** ⭐ (Implemented)

The greeting server now supports both MCP protocol and HTTP endpoints:

#### **HTTP REST Endpoints:**
- `GET /` - Service information and available endpoints
- `GET /health` - Health check
- `GET /greet/{name}` - REST API for greeting
- `GET /farewell/{name}` - REST API for farewell

#### **JSON-RPC MCP Endpoints:**
- `POST /mcp` - MCP JSON-RPC protocol
- `POST /jsonrpc` - Alternative MCP endpoint

#### **Supported MCP Methods:**
- `initialize` - MCP protocol initialization
- `tools/list` - List available tools
- `tools/call` - Call MCP tools (greet, farewell)

## 📁 **File Structure**

```
greeting_mcp_server.py     # Enhanced server with HTTP support
Dockerfile.greeting-mcp    # Updated Docker configuration
docker-compose.yml         # Container orchestration
nginx-gateway.conf         # NGINX routing configuration
test_http_endpoints.py     # Comprehensive HTTP testing
```

## 🚀 **Usage Examples**

### **REST API Usage:**

```bash
# Get service info
curl -sk https://mcp.local/greeting/

# Health check
curl -sk https://mcp.local/greeting/health

# Greet someone
curl -sk https://mcp.local/greeting/greet/Alice

# Say farewell
curl -sk https://mcp.local/greeting/farewell/Bob
```

### **JSON-RPC MCP Usage:**

```bash
# Initialize MCP session
curl -sk -H "Content-Type: application/json" -d '{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "initialize",
  "params": {
    "protocolVersion": "2024-11-05",
    "capabilities": {},
    "clientInfo": {"name": "test", "version": "1.0"}
  }
}' https://mcp.local/greeting/mcp

# List available tools
curl -sk -H "Content-Type: application/json" -d '{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "tools/list"
}' https://mcp.local/greeting/mcp

# Call greet tool
curl -sk -H "Content-Type: application/json" -d '{
  "jsonrpc": "2.0",
  "id": 3,
  "method": "tools/call",
  "params": {
    "name": "greet",
    "arguments": {"name": "Charlie"}
  }
}' https://mcp.local/greeting/mcp
```

## ⚙️ **Configuration**

### **Environment Variables:**

- `RUN_MODE`: Set to `"http"` for HTTP mode, `"stdio"` for MCP stdio mode
- `SERVER_PORT`: HTTP server port (default: 8001)
- `HEALTH_PORT`: Health check port (default: 8001)

### **Docker Configuration:**

```yaml
environment:
  RUN_MODE: "http"          # Enable HTTP mode
  SERVER_PORT: "8001"       # HTTP server port
  HEALTH_PORT: "8001"       # Health check port
expose:
  - "8001"                  # Expose HTTP port
```

### **NGINX Configuration:**

```nginx
upstream greeting-mcp-backend {
    server greeting-mcp:8001 max_fails=3 fail_timeout=30s;
}

location /greeting/ {
    rewrite ^/greeting/(.*)$ /$1 break;
    proxy_pass http://greeting-mcp-backend;
    # ... proxy headers and settings
}
```

## 🧪 **Testing**

### **Available Test Scripts:**

```bash
# Basic connectivity tests
make test-simple

# HTTP endpoint comprehensive tests
make test-http

# Full test suite (bash)
make test-full

# Python MCP protocol tests
make test-python
```

### **Manual Testing:**

```bash
# Start services
make up

# Test HTTP endpoints
python3 test_http_endpoints.py

# Check logs
make logs-greeting-mcp
```

## 🔍 **Key Implementation Details**

### **1. HTTP Server Integration**

The `HealthHandler` class extends `BaseHTTPRequestHandler` to provide:
- RESTful endpoints for direct web access
- JSON-RPC endpoint for MCP protocol compatibility
- Proper error handling and validation
- JSON response formatting

### **2. Dual Mode Operation**

```python
if run_mode == 'http':
    # HTTP mode: Web accessible
    start_http_server()
else:
    # stdio mode: Traditional MCP
    mcp.run(transport='stdio')
```

### **3. MCP Protocol Bridge**

The HTTP server translates JSON-RPC requests to MCP tool calls:
- Validates MCP protocol structure
- Calls FastMCP tools internally
- Returns properly formatted MCP responses

### **4. NGINX Integration**

- **Path Rewriting**: `/greeting/path` → `/path`
- **Header Forwarding**: Maintains client information
- **Health Checks**: Automated container health monitoring
- **SSL Termination**: HTTPS to HTTP conversion

## 🎯 **Benefits**

- ✅ **Web Accessibility**: Direct browser/curl access
- ✅ **Protocol Compatibility**: Maintains MCP standard compliance
- ✅ **Dual Interface**: Both REST and JSON-RPC support
- ✅ **Container Ready**: Docker and NGINX integration
- ✅ **Health Monitoring**: Automated health checks
- ✅ **Scalable**: Load balancing ready

## 🔗 **Access URLs**

After deployment:

- **Service Root**: `https://mcp.local/greeting/`
- **Health Check**: `https://mcp.local/greeting/health`
- **REST API**: `https://mcp.local/greeting/greet/Alice`
- **MCP Protocol**: `https://mcp.local/greeting/mcp`

## 📝 **Next Steps**

1. **Authentication**: Add API key or OAuth support
2. **Rate Limiting**: Implement request throttling
3. **Caching**: Add response caching for performance
4. **Monitoring**: Integrate with monitoring systems
5. **Documentation**: Auto-generate API documentation

This implementation provides a complete solution for exposing MCP servers over HTTP while maintaining protocol compatibility and adding web accessibility.