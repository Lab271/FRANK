# FRANK MCP Server - Implementation Outline

## Overview
A Model Context Protocol (MCP) server that exposes FRANK threat intelligence platform capabilities to AI assistants and other MCP clients. Inspired by `stages/stage3/frank_stage3.py` with support for both LocalStack (Docker) and AWS environments.

## Architecture

### Core Components

```
frank_mcp_server.py
├── Configuration Layer
│   ├── Environment detection (LocalStack vs AWS)
│   ├── Database connection settings
│   ├── Authentication settings (optional)
│   └── Logging configuration
│
├── Database Layer
│   ├── DynamoDB connection (via frank.storage)
│   ├── Support for LocalStack endpoint
│   └── Support for AWS direct connection
│
├── MCP Server Layer (FastMCP)
│   ├── Tools (threat intelligence queries)
│   ├── Resources (configuration, statistics)
│   └── Prompts (usage guidance)
│
└── Initialization & Main
    ├── Argument parsing
    ├── Environment setup
    └── Server startup
```

## Configuration Management

### Environment Variables
```python
# Environment Selection
FRANK_ENVIRONMENT = "localstack" | "aws"

# AWS Configuration
AWS_DEFAULT_REGION = "eu-west-1"
AWS_PROFILE = None | "profile-name"
AWS_ACCESS_KEY_ID = "test" (for LocalStack)
AWS_SECRET_ACCESS_KEY = "test" (for LocalStack)

# DynamoDB Configuration
ENDPOINT = "http://localhost:4566" | None (None for AWS)
DYNAMODB_TABLE = "frank-data"
DYNAMODB_AUDIT_TABLE = "frank-audit-table"

# Logging
LOG_LEVEL = "debug" | "info" | "warning" | "error"
SILENT = "False" | "True"
```

### Configuration Function
```python
@lru_cache()
def get_config() -> Dict[str, Any]:
    """
    Get MCP server configuration from environment.
    Similar to frank_stage3.py but MCP-focused.
    """
    return {
        "endpoint": ...,        # None for AWS, URL for LocalStack
        "environment": ...,     # "aws" or "localstack"
        "region": ...,
        "table_name": ...,
        "audit_table_name": ...,
        # ... other settings
    }
```

## MCP Server Implementation (FastMCP)

### Server Initialization
```python
from mcp.server.fastmcp.server import FastMCP
from frank.storage import create_dynamodb_database
from frank.util.server import create_server

# Initialize MCP server
mcp = FastMCP("frank_threat_intel")

# Initialize FRANK components (lazy loading)
_server = None

def get_frank_server():
    """Lazy initialization of FRANK server"""
    global _server
    if _server is None:
        config = get_config()
        logger = get_module_logger("frank.mcp")
        db = create_dynamodb_database(config=config, logger=logger)
        _server = create_server(db=db, config=config, logger=logger)
    return _server
```

### MCP Tools

#### 1. Query Sightings by Observable
```python
@mcp.tool()
def query_sightings_by_observable(
    observable_value: str,
    observable_type: str = None,
    limit: int = 10
) -> str:
    """
    Query threat intelligence sightings by observable value.
    
    Args:
        observable_value: IP address, domain, hash, etc.
        observable_type: Type filter (ipv4-addr, domain-name, etc.)
        limit: Maximum results to return (default: 10)
    
    Returns:
        JSON string with sighting data
    """
    # Implementation:
    # 1. Create mock user context (or use system access level)
    # 2. Query via get_server().get_sightings_from_observations()
    # 3. Format results as JSON
    # 4. Return formatted string
```

#### 2. Get Submission by ID
```python
@mcp.tool()
def get_submission(submission_id: str) -> str:
    """
    Retrieve a specific threat intelligence submission by ID.
    
    Args:
        submission_id: STIX-formatted submission identifier
    
    Returns:
        JSON string with submission details or error message
    """
    # Implementation:
    # 1. Create mock user context
    # 2. Call get_server().get_submission_by_id()
    # 3. Format as JSON
    # 4. Handle not found cases
```

#### 3. Get Platform Statistics
```python
@mcp.tool()
def get_platform_stats(days: int = 30) -> str:
    """
    Get FRANK platform statistics for the last N days.
    
    Args:
        days: Number of days to include (default: 30)
    
    Returns:
        JSON string with platform statistics
    """
    # Implementation:
    # 1. Get health check data
    # 2. Get database statistics (if available)
    # 3. Format as readable summary
```

#### 4. Search by Threat Context
```python
@mcp.tool()
def search_by_campaign(campaign_name: str, limit: int = 10) -> str:
    """
    Search for sightings related to a specific campaign.
    
    Args:
        campaign_name: Name of the threat campaign
        limit: Maximum results to return
    
    Returns:
        JSON string with matching sightings
    """
    # Implementation (if supported by FRANK):
    # 1. Query database with campaign filter
    # 2. Return formatted results
```

### MCP Resources

#### 1. Configuration Resource
```python
@mcp.resource(uri="frank://config")
def get_frank_config() -> str:
    """
    Expose FRANK MCP server configuration.
    
    Returns:
        JSON string with configuration details
    """
    config = get_config()
    return json.dumps({
        "environment": config["environment"],
        "region": config["region"],
        "table_name": config["table_name"],
        "endpoint": config["endpoint"] or "AWS Direct",
        "version": frank.__version__,
    }, indent=2)
```

#### 2. Observable Types Resource
```python
@mcp.resource(uri="frank://observable-types")
def get_observable_types() -> str:
    """
    List available observable types in FRANK.
    
    Returns:
        JSON string with observable type definitions
    """
    from frank.core.enum import ObservableType
    types = {t.value: t.name for t in ObservableType}
    return json.dumps(types, indent=2)
```

#### 3. Access Tiers Resource
```python
@mcp.resource(uri="frank://access-tiers")
def get_access_tiers() -> str:
    """
    List FRANK access tier levels.
    
    Returns:
        JSON string with access tier information
    """
    from frank.core.enum import AccessTier
    tiers = {
        t.value: {
            "name": t.name,
            "level": t.value,
        } for t in AccessTier
    }
    return json.dumps(tiers, indent=2)
```

### MCP Prompts

```python
@mcp.prompt()
def frank_usage_prompt() -> str:
    """
    Provide usage guidance for FRANK MCP tools.
    """
    return """
    You are interacting with the FRANK Threat Intelligence Platform via MCP.
    
    Available tools:
    1. 'query_sightings_by_observable' - Search for threat sightings by observable value
       Example: query_sightings_by_observable("185.220.102.45", "ipv4-addr", 10)
    
    2. 'get_submission' - Retrieve a specific submission by ID
       Example: get_submission("submission--1234abcd-12ab-34cd-56ef-1234567890ab")
    
    3. 'get_platform_stats' - Get platform statistics for the last N days
       Example: get_platform_stats(30)
    
    4. 'search_by_campaign' - Search for sightings related to a threat campaign
       Example: search_by_campaign("banking_campaign_2025", 10)
    
    Available resources:
    - frank://config - Server configuration
    - frank://observable-types - Available observable types
    - frank://access-tiers - Access tier information
    
    Note: This MCP server operates with system-level access to FRANK data.
    All queries are read-only and do not modify the database.
    """
```

## Main Function & Startup

### Argument Parsing
```python
def main():
    """
    Main function with argument parsing for flexible configuration.
    Inspired by frank_stage3.py main() function.
    """
    parser = argparse.ArgumentParser(
        description="FRANK MCP Server - Threat Intelligence Query Interface"
    )
    
    # Environment configuration
    parser.add_argument(
        "--environment",
        type=str,
        default=os.getenv("FRANK_ENVIRONMENT", "localstack"),
        choices=["localstack", "aws"],
        help="Configuration environment"
    )
    
    # AWS configuration
    parser.add_argument("--region", type=str, default="eu-west-1")
    parser.add_argument("--profile", type=str, default=None)
    parser.add_argument("--endpoint", type=str, default="http://localhost:4566")
    
    # DynamoDB configuration
    parser.add_argument("--table-name", type=str, default="frank-data")
    parser.add_argument("--audit-table-name", type=str, default="frank-audit-table")
    
    # Logging configuration
    parser.add_argument(
        "--log-level",
        choices=["debug", "info", "warning", "error"],
        default="info"
    )
    parser.add_argument("--silent", action="store_true")
    
    args = parser.parse_args()
    
    # Set environment variables
    setup_environment(args)
    
    # Setup logging
    logger = setup_logging(silent=args.silent)
    
    # Log startup info
    log_startup_info(logger, args)
    
    # Run MCP server
    mcp.run(transport='stdio')
```

### Environment Setup
```python
def setup_environment(args):
    """
    Configure environment variables based on arguments.
    Ensures proper settings for LocalStack or AWS.
    """
    os.environ["FRANK_ENVIRONMENT"] = args.environment
    os.environ["AWS_DEFAULT_REGION"] = args.region
    
    if args.environment == "localstack":
        os.environ["ENDPOINT"] = args.endpoint
        os.environ["AWS_ACCESS_KEY_ID"] = "test"
        os.environ["AWS_SECRET_ACCESS_KEY"] = "test"
    elif args.environment == "aws":
        os.environ.pop("ENDPOINT", None)
        if args.profile:
            os.environ["AWS_PROFILE"] = args.profile
    
    os.environ["DYNAMODB_TABLE"] = args.table_name
    os.environ["DYNAMODB_AUDIT_TABLE"] = args.audit_table_name
```

## Usage Examples

### Running with LocalStack (Docker)
```bash
# Start LocalStack DynamoDB
cd stages/stage3/local
docker-compose up -d dynamodb

# Run FRANK MCP server pointing to LocalStack
python frank_mcp_server.py \
    --environment localstack \
    --endpoint http://localhost:4566 \
    --table-name frank-data \
    --log-level info

# Or with environment variables
FRANK_ENVIRONMENT=localstack \
ENDPOINT=http://localhost:4566 \
python frank_mcp_server.py
```

### Running with AWS Direct
```bash
# Run FRANK MCP server pointing to AWS
python frank_mcp_server.py \
    --environment aws \
    --region eu-west-1 \
    --profile my-aws-profile \
    --table-name frank-production-data \
    --log-level warning

# Or with environment variables
FRANK_ENVIRONMENT=aws \
AWS_PROFILE=my-aws-profile \
AWS_DEFAULT_REGION=eu-west-1 \
python frank_mcp_server.py
```

### MCP Client Configuration
Add to Cline's MCP settings:
```json
{
  "mcpServers": {
    "frank_threat_intel": {
      "command": "uv",
      "args": [
        "--directory",
        "/path/to/FRANK",
        "run",
        "python",
        "tests/spikes/014_mcp/frank_mcp_server.py",
        "--environment",
        "localstack",
        "--log-level",
        "info"
      ]
    }
  }
}
```

## Error Handling

### Database Connection Errors
```python
def get_frank_server():
    """Lazy initialization with error handling"""
    global _server
    if _server is None:
        try:
            config = get_config()
            logger = get_module_logger("frank.mcp")
            db = create_dynamodb_database(config=config, logger=logger)
            _server = create_server(db=db, config=config, logger=logger)
            logger.info("FRANK server initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize FRANK server: {e}")
            raise
    return _server
```

### Tool Execution Errors
```python
@mcp.tool()
def query_sightings_by_observable(...) -> str:
    try:
        server = get_frank_server()
        # ... query logic
        return json.dumps(results)
    except Exception as e:
        logger.error(f"Query failed: {e}")
        return json.dumps({
            "error": str(e),
            "status": "failed"
        })
```

## Testing

### Local Testing with LocalStack
```python
# test_frank_mcp_server.py
def test_query_sightings():
    """Test querying sightings via MCP tool"""
    # Setup LocalStack environment
    os.environ["FRANK_ENVIRONMENT"] = "localstack"
    os.environ["ENDPOINT"] = "http://localhost:4566"
    
    # Import and test
    from frank_mcp_server import query_sightings_by_observable
    result = query_sightings_by_observable("185.220.102.45")
    assert "sightings" in json.loads(result)
```

### Integration Testing
```bash
# Test with MCP Inspector
npx @modelcontextprotocol/inspector \
    python frank_mcp_server.py --environment localstack
```

## Dependencies

### Required Packages
```python
# Core FRANK
frank>=0.1.0

# MCP
mcp>=1.0.0

# AWS
boto3>=1.28.0

# Utilities
pydantic>=2.0.0
```

### Installation
```bash
# Install in development mode
pip install -e .

# Or with uv
uv pip install -e .
```

## Security Considerations

1. **Read-Only Access**: MCP server operates in read-only mode
2. **System Access Level**: Uses elevated access for querying (configurable)
3. **No Authentication**: Direct database access (authentication at MCP client level)
4. **Data Filtering**: Can implement access level filtering in tool responses
5. **Audit Logging**: Leverages FRANK's audit table for query tracking

## Future Enhancements

1. **Submission Tools**: Add write capability for submitting threat intelligence
2. **Real-time Updates**: Implement streaming for new sightings
3. **Advanced Filtering**: More sophisticated query capabilities
4. **Authentication**: Add token-based authentication for MCP tools
5. **Caching**: Implement caching for frequently accessed data
6. **Multi-tenancy**: Support multiple organizations with access control

## File Structure

```
tests/spikes/014_mcp/
├── frank_mcp_server.py           # Main MCP server implementation
├── test_frank_mcp_server.py      # Unit tests
├── FRANK_MCP_SERVER_OUTLINE.md   # This document
├── README_FRANK_MCP.md           # User-facing documentation
└── frank_mcp_config.json         # Example MCP client config
