# https://medium.com/@ankitfotografia/getting-started-with-the-mcp-python-sdk-development-testing-and-beyond-with-mcp-inspector-dd40a255ac3d
from mcp.server.fastmcp.server import FastMCP 
import json
import random

# FastMCP Initialization
mcp = FastMCP("greetings")

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

if __name__ == "__main__":
    mcp.run(transport='stdio')
