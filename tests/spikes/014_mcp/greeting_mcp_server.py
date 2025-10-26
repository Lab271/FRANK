# https://medium.com/@ankitfotografia/getting-started-with-the-mcp-python-sdk-development-testing-and-beyond-with-mcp-inspector-dd40a255ac3d
from mcp.server.fastmcp.server import FastMCP 
import json
import random

# FastMCP Initialization
mcp = FastMCP("greetings")

@mcp.prompt()
def greeting_prompt():
    return """
    You are interacting with a greeting service that uses a configuration file ('greetings_style.json') to load greeting styles. Call the 'greet' tool with a single parameter: a name (string).
    The name must be alphabetic characters only, max 20 characters, The server will respond with a personalized greeting, randomly selected from available styles in the configuration, such as 'Hello, {name}!', 'Hi there, {name}!', or 'Greetings, {name}!'.
    Example: Call greet("Alice") to receive a greeting like 'Greetings, Alice!, Welcome to the team' or another style from the configuration.
    """

@mcp.resource(uri="file://greeting_style.json")
def load_greeting_data():
    # Load from a file named 'greeting_style.json'
    with open("greeting_style.json", "r") as f:
        data = json.load(f)
    return data

@mcp.tool()
def greet(name: str) -> str:
    greeting_data = load_greeting_data()  # Defined under @mcp.resource
    greeting_styles = greeting_data["greeting_styles"]
    # Select a random greeting style
    greeting_template = random.choice(greeting_styles)
    return greeting_template.format(name=name)

if __name__ == "__main__":
    mcp.run(transport='stdio')
