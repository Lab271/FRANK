# Greeting MCP Server

A Model Context Protocol (MCP) server that provides greeting and farewell functionality with configurable styles.

## Features

- **Greet Tool**: Generate personalized greetings using random greeting styles
- **Farewell Tool**: Generate personalized farewells using random farewell styles  
- **Configurable Styles**: JSON configuration file for customizing greeting and farewell templates
- **Health Check**: HTTP health endpoint for monitoring

## Configuration

The greeting styles are configured in `greeting_style.json`:

```json
{
  "greeting_styles": [
    "Hello, {name}! Good to see you !!",
    "Hi there, {name}!, Welcome to the Class",
    "Greetings, {name}!, Welcome to the team"
  ],
  "farewell_styles": [
    "Goodbye, {name}! See you soon!",
    "Farewell, {name}! Take care!",
    "See you later, {name}! Have a great day!",
    "Until next time, {name}! Stay awesome!"
  ]
}
```

## Available Tools

### greet(name: str) -> str
Greets a person with a randomly selected greeting style.

**Parameters:**
- `name`: A string containing the person's name (max 20 characters, alphabetic only)

**Example:**
```python
greet("Alice")  # Returns: "Greetings, Alice!, Welcome to the team"
```

### farewell(name: str) -> str  
Says goodbye to a person with a randomly selected farewell style.

**Parameters:**
- `name`: A string containing the person's name (max 20 characters, alphabetic only)

**Example:**
```python
farewell("Bob")  # Returns: "Goodbye, Bob! See you soon!"
```

## Docker Deployment

The greeting MCP server runs in its own Docker container and is accessible via the gateway at:

- **Gateway**: `https://mcp.local/greeting/`
- **Health Check**: `https://mcp.local/greeting/health`

### Container Details

- **Container Name**: `mcp-greeting-server`
- **Internal Port**: `8001`
- **Health Check Port**: `8001`
- **Base Image**: `python:3.11-slim`

### Environment Variables

- `LOG_LEVEL`: Logging level (default: info)
- `PYTHONUNBUFFERED`: Python output buffering (set to "1")
- `SERVER_NAME`: Service name (greeting-mcp)
- `SERVER_PORT`: Server port (8001)
- `HEALTH_PORT`: Health check port (8001)

## Testing

Test the greeting service with multiple options:

### Quick Tests
```bash
# Basic health check
make test-greeting-mcp

# Manual curl test
curl -sk https://mcp.local/greeting/health
```

### Comprehensive Testing
```bash
# Full test suite (bash script)
make test-full
# or directly: ./test_greeting_server.sh

# Python test suite (comprehensive)
make test-python
# or directly: python3 test_greeting_python.py

# Simple Python tests
make test-simple
# or directly: python3 test_greeting_simple.py
```

### Test Scripts Available
- **`test_greeting_server.sh`** - Comprehensive bash-based testing with JSON-RPC protocol tests
- **`test_greeting_python.py`** - Advanced Python testing with detailed reporting
- **`test_greeting_simple.py`** - Simple Python script for basic connectivity tests
- **`manual_test_commands.txt`** - Copy-paste ready curl commands for manual testing

### Test Features
- ✅ Gateway health and service discovery
- ✅ Greeting service health endpoint
- ✅ SSL certificate validation (self-signed)
- ✅ Error handling (404, timeouts)
- ✅ Performance measurement
- ✅ JSON-RPC protocol testing (if implemented)
- ✅ Container connectivity validation

## Logs

View greeting service logs:

```bash
# Follow logs
make logs-greeting-mcp

# View all service logs
make logs
```

## Development

The server is built with the FastMCP framework and includes:

- HTTP health check server running in a background thread
- JSON resource loading for configuration
- Random style selection for variety
- Input validation for names