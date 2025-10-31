# https://medium.com/@ankitfotografia/getting-started-with-the-mcp-python-sdk-development-testing-and-beyond-with-mcp-inspector-dd40a255ac3d
import argparse
import random
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import os
import json

from mcp.server.fastmcp.server import FastMCP 

# FastMCP Initialization
mcp = FastMCP("greetings")

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/health':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(b'{"status": "healthy", "service": "greeting-mcp"}')
        elif self.path.startswith('/greet/'):
            # Extract name from URL path: /greet/Alice
            name = self.path[7:]  # Remove '/greet/' prefix
            if name and len(name) <= 20 and name.isalpha():
                try:
                    greeting = greet(name)
                    response = {"greeting": greeting, "name": name}
                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps(response).encode())
                except Exception as e:
                    self.send_error(500, f"Error generating greeting: {str(e)}")
            else:
                self.send_error(400, "Invalid name. Must be alphabetic, max 20 characters.")
        elif self.path.startswith('/farewell/'):
            # Extract name from URL path: /farewell/Bob
            name = self.path[10:]  # Remove '/farewell/' prefix
            if name and len(name) <= 20 and name.isalpha():
                try:
                    farewell_msg = farewell(name)
                    response = {"farewell": farewell_msg, "name": name}
                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps(response).encode())
                except Exception as e:
                    self.send_error(500, f"Error generating farewell: {str(e)}")
            else:
                self.send_error(400, "Invalid name. Must be alphabetic, max 20 characters.")
        elif self.path == '/':
            # Root endpoint - show available endpoints
            response = {
                "service": "greeting-mcp",
                "status": "healthy",
                "endpoints": {
                    "health": "/health",
                    "greet": "/greet/{name}",
                    "farewell": "/farewell/{name}"
                },
                "examples": {
                    "greet": "/greet/Alice",
                    "farewell": "/farewell/Bob"
                }
            }
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(response).encode())
        else:
            self.send_response(404)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            error_response = {"error": "Not Found", "path": self.path}
            self.wfile.write(json.dumps(error_response).encode())
    
    def do_POST(self):
        if self.path == '/mcp' or self.path == '/jsonrpc':
            # Handle JSON-RPC requests for MCP protocol
            content_length = int(self.headers.get('Content-Length', 0))
            if content_length > 0:
                post_data = self.rfile.read(content_length)
                try:
                    request = json.loads(post_data.decode())
                    response = self.handle_jsonrpc_request(request)
                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps(response).encode())
                except Exception as e:
                    error_response = {
                        "jsonrpc": "2.0",
                        "error": {"code": -32603, "message": f"Internal error: {str(e)}"},
                        "id": None
                    }
                    self.send_response(500)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps(error_response).encode())
            else:
                self.send_error(400, "No data received")
        else:
            self.send_error(404, "Endpoint not found")
    
    def handle_jsonrpc_request(self, request):
        """Handle JSON-RPC requests for MCP protocol"""
        method = request.get("method")
        params = request.get("params", {})
        request_id = request.get("id")
        
        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {
                        "tools": {
                            "listChanged": False
                        }
                    },
                    "serverInfo": {
                        "name": "greeting-mcp",
                        "version": "1.0.0"
                    }
                },
                "id": request_id
            }
        elif method == "tools/list":
            return {
                "jsonrpc": "2.0",
                "result": {
                    "tools": [
                        {
                            "name": "greet",
                            "description": "Greet a person with a randomly selected greeting style",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "name": {
                                        "type": "string",
                                        "description": "The name of the person to greet (max 20 characters, alphabetic only)"
                                    }
                                },
                                "required": ["name"]
                            }
                        },
                        {
                            "name": "farewell",
                            "description": "Say goodbye to a person with a randomly selected farewell style",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "name": {
                                        "type": "string",
                                        "description": "The name of the person to say goodbye to (max 20 characters, alphabetic only)"
                                    }
                                },
                                "required": ["name"]
                            }
                        }
                    ]
                },
                "id": request_id
            }
        elif method == "tools/call":
            tool_name = params.get("name")
            arguments = params.get("arguments", {})
            
            if tool_name == "greet":
                name = arguments.get("name", "")
                if name and len(name) <= 20 and name.isalpha():
                    greeting_text = greet(name)
                    return {
                        "jsonrpc": "2.0",
                        "result": {
                            "content": [
                                {
                                    "type": "text",
                                    "text": greeting_text
                                }
                            ]
                        },
                        "id": request_id
                    }
                else:
                    return {
                        "jsonrpc": "2.0",
                        "error": {
                            "code": -32602,
                            "message": "Invalid name. Must be alphabetic, max 20 characters."
                        },
                        "id": request_id
                    }
            elif tool_name == "farewell":
                name = arguments.get("name", "")
                if name and len(name) <= 20 and name.isalpha():
                    farewell_text = farewell(name)
                    return {
                        "jsonrpc": "2.0",
                        "result": {
                            "content": [
                                {
                                    "type": "text",
                                    "text": farewell_text
                                }
                            ]
                        },
                        "id": request_id
                    }
                else:
                    return {
                        "jsonrpc": "2.0",
                        "error": {
                            "code": -32602,
                            "message": "Invalid name. Must be alphabetic, max 20 characters."
                        },
                        "id": request_id
                    }
            else:
                return {
                    "jsonrpc": "2.0",
                    "error": {
                        "code": -32601,
                        "message": f"Unknown tool: {tool_name}"
                    },
                    "id": request_id
                }
        else:
            return {
                "jsonrpc": "2.0",
                "error": {
                    "code": -32601,
                    "message": f"Unknown method: {method}"
                },
                "id": request_id
            }
    
    # def log_message(self, format, *args):
    #     # Suppress default HTTP server logging
    #     pass

def start_health_server():
    """Start HTTP health check server in a separate thread"""
    port = int(os.environ.get('HEALTH_PORT', '8001'))
    server = HTTPServer(('0.0.0.0', port), HealthHandler)
    server.serve_forever()

def start_http_server():
    """Start HTTP server for web API access"""
    port = int(os.environ.get('SERVER_PORT', '8001'))
    server = HTTPServer(('0.0.0.0', port), HealthHandler)
    server.serve_forever()

@mcp.prompt()
def greeting_prompt():
    return """
    You are interacting with a greeting service that uses a configuration file ('greetings_style.json') to load greeting and farewell styles.
    
    Available tools:
    1. 'greet' - Call with a single parameter: a name (string). The name must be alphabetic characters only, max 20 characters. 
       The server will respond with a personalized greeting, randomly selected from available styles.
       Example: Call greet("Alice") to receive a greeting like 'Greetings, Alice!, Welcome to the team'
    
    2. 'farewell' - Call with a single parameter: a name (string). The name must be alphabetic characters only, max 20 characters.
       The server will respond with a personalized farewell, randomly selected from available farewell styles.
       Example: Call farewell("Bob") to receive a farewell like 'Goodbye, Bob! See you soon!'
    """

@mcp.resource(uri="file://greeting_style.json")
def load_greeting_data():
    # Load from a file named 'greeting_style.json'
    with open("greeting_style.json", "r") as f:
        data = json.load(f)
    return data

@mcp.tool()
def greet(name: str) -> str:
    """Greet a person with a randomly selected greeting style"""
    greeting_data = load_greeting_data()  # Defined under @mcp.resource
    greeting_styles = greeting_data["greeting_styles"]
    # Select a random greeting style
    greeting_template = random.choice(greeting_styles)
    return greeting_template.format(name=name)

@mcp.tool()
def farewell(name: str) -> str:
    """Say goodbye to a person with a randomly selected farewell style"""
    greeting_data = load_greeting_data()  # Defined under @mcp.resource
    farewell_styles = greeting_data["farewell_styles"]
    # Select a random farewell style
    farewell_template = random.choice(farewell_styles)
    return farewell_template.format(name=name)

# ===================================
# Environment Setup
# ===================================
def setup_logging(silent: bool = False):
    """
    Setup logging configuration.
    
    Args:
        silent: If True, suppress logging output.
    """
    import logging
    logger = logging.getLogger("greeting-mcp")
    # handler = logging.StreamHandler()
    # formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    # handler.setFormatter(formatter)
    # logger.addHandler(handler)
    
    if silent:
        logger.setLevel(logging.CRITICAL)
    else:
        logger.setLevel(logging.INFO)
    
    return logger



def log_startup_info(logger, args):
    """
    Log startup information based on command-line arguments.
    Provides insights into the configured environment and settings.
    
    Args:
        args: Parsed command-line arguments
    """
    logger.info("Starting Greeting MCP Server with the following configuration:")
    logger.info(f"  Run Mode: {args.run_mode}")
    logger.info(f"  Log Level: {args.log_level}")
    logger.info(f"  Silent Mode: {args.silent}")

def setup_environment(args):
    """
    Log startup information based on command-line arguments.
    Provides insights into the configured environment and settings.

    Args:
        args: Parsed command-line arguments
    """
    os.environ['MCP_TRANSPORT'] = args.run_mode
    os.environ['LOG_LEVEL'] = args.log_level
    os.environ['SILENT'] = str(args.silent)

# ===================================
# Main Function
# ===================================

def main():
    """
    Main function with argument parsing for flexible MCP server configuration.
    """
    parser = argparse.ArgumentParser(
        description="Greeting MCP Server with configurable options.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run with stdio
  %(prog)s --run-mode stdio
        """
    )
    
    # Environment configuration
    
    # Logging configuration
    parser.add_argument(
        "--log-level",
        type=str,
        default=os.getenv("LOG_LEVEL", "info"),
        choices=["debug", "info", "warning", "error"],
        help="Logging level (default: LOG_LEVEL or 'info')"
    )
    parser.add_argument(
        "-s", "--silent",
        action="store_true",
        default=os.getenv("SILENT", "False").lower() in ("true", "1", "yes"),
        help="Enable silent mode (default: SILENT or False)"
    )
    
    # MCP Server configuration
    parser.add_argument(
        "-m", "--run-mode",
        type=str,
        default=os.getenv("MCP_TRANSPORT", "stdio"),
        choices=["stdio", "http"],
        help="MCP server transport mode (default: MCP_TRANSPORT or 'stdio')"
    )
    
    args = parser.parse_args()
    
    # Set environment variables
    setup_environment(args)
    
    # Setup logging
    if args.silent:
        logger = setup_logging(silent=True)
    else:
        logger = setup_logging(silent=False)
        log_startup_info(logger, args)
    
    # Run MCP server
    try:
        if args.run_mode == 'http':
            logger.info("Starting MCP server via HTTP transport...")
            # Start HTTP server directly (includes health endpoint)
            start_http_server()
        else:
            logger.info("Starting MCP server via stdio transport...")
            # Start health check server in background thread
            health_thread = threading.Thread(target=start_health_server, daemon=True)
            health_thread.start()
            
            # Start MCP server
            mcp.run(transport='stdio')
            
    except KeyboardInterrupt:
        logger.info("MCP server stopped by user")
    except Exception as e:
        logger.error(f"MCP server failed: {e}")
        raise


if __name__ == "__main__":
    main()
    

