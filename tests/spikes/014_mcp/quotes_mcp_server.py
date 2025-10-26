# Famous Quotes MCP Server
from mcp.server.fastmcp.server import FastMCP 
import json
import random

# FastMCP Initialization
mcp = FastMCP("famous_quotes")

@mcp.prompt()
def quotes_prompt():
    return """
    You are interacting with a famous quotes service that uses a configuration file ('famous_quotes.json') to load quotes from movies and famous people.
    
    Available tools:
    1. 'get_movie_quote' - Call with a single parameter: a movie name (string). 
       The server will respond with a random quote from that movie.
       Available movies: Gone with the Wind, The Godfather, Casablanca, The Wizard of Oz, Star Wars, Forrest Gump, E.T., Apollo 13, Jaws, Titanic
       Example: Call get_movie_quote("The Godfather") to receive a random quote from The Godfather
    
    2. 'get_person_quote' - Call with a single parameter: a person's name (string).
       The server will respond with a random quote from that person.
       Available people: William Shakespeare, John Kennedy
       Example: Call get_person_quote("William Shakespeare") to receive a random Shakespeare quote
    
    3. 'guess_movie_from_quote' - Call with a single parameter: a quote (string).
       The server will search through all movie quotes and return the movie it's from.
       Example: Call guess_movie_from_quote("May the Force be with you") to find out it's from Star Wars
    """

@mcp.resource(uri="file://famous_quotes.json/")
def load_quotes_data():
    # Load from a file named 'famous_quotes.json'
    with open("famous_quotes.json", "r") as f:
        data = json.load(f)
    return data

@mcp.tool()
def get_movie_quote(name: str) -> str:
    """Get a random quote from a movie by its name"""
    quotes_data = load_quotes_data()  # Defined under @mcp.resource
    movie_quotes = quotes_data["movie_quotes"]
    
    # Check if the movie exists
    if name not in movie_quotes:
        available_movies = ", ".join(movie_quotes.keys())
        return f"Movie '{name}' not found. Available movies: {available_movies}"
    
    # Get movie data
    movie_data = movie_quotes[name]
    year = movie_data["year"]
    quotes_list = movie_data["quotes"]
    
    # Select a random quote
    random_quote = random.choice(quotes_list)
    
    return f'"{random_quote}" - *{name}* ({year})'

@mcp.tool()
def get_person_quote(name: str) -> str:
    """Get a random quote from a famous person by their name"""
    quotes_data = load_quotes_data()  # Defined under @mcp.resource
    person_quotes = quotes_data["person_quotes"]
    
    # Check if the person exists
    if name not in person_quotes:
        available_people = ", ".join(person_quotes.keys())
        return f"Person '{name}' not found. Available people: {available_people}"
    
    # Get person's quotes
    quotes_list = person_quotes[name]["quotes"]
    
    # Select a random quote
    random_quote = random.choice(quotes_list)
    
    return f'"{random_quote}" - {name}'

@mcp.tool()
def guess_movie_from_quote(quote: str) -> str:
    """Guess which movie a quote is from by searching through all movie quotes"""
    quotes_data = load_quotes_data()  # Defined under @mcp.resource
    movie_quotes = quotes_data["movie_quotes"]
    
    # Normalize the input quote for comparison (strip quotes and whitespace, lowercase)
    normalized_input = quote.strip().strip('"').strip("'").lower()
    
    # Search through all movies and their quotes
    for movie_name, movie_data in movie_quotes.items():
        for movie_quote in movie_data["quotes"]:
            # Normalize the stored quote for comparison
            normalized_stored = movie_quote.lower()
            
            # Check for exact match or if the input is contained in the stored quote
            if normalized_input == normalized_stored or normalized_input in normalized_stored:
                year = movie_data["year"]
                return f'That quote is from *{movie_name}* ({year}): "{movie_quote}"'
    
    # If no match found
    return f'Could not find a movie match for: "{quote}". Try providing a more complete or exact quote from the database.'

if __name__ == "__main__":
    mcp.run(transport='stdio')
