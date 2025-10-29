# Lease Calculator MCP Server
from mcp.server.fastmcp.server import FastMCP 

# FastMCP Initialization
mcp = FastMCP("lease_calculator")

@mcp.prompt()
def lease_calculator_prompt():
    return """
    You are interacting with a lease calculator service that calculates monthly lease fees based on age and salary.
    
    Available tools:
    1. 'calculate_lease_fee' - Call with two parameters: age (integer) and salary (float/integer). 
       The server will calculate the monthly lease fee based on the following rules:
       - Base calculation: A salary of 100,000 equals 1,000 euro per month
       - The lease amount increases proportionally with salary
       - Age discount: If the person is below 30 years old, they receive a 200 euro discount
       
       Examples: 
       - calculate_lease_fee(35, 100000) returns 1000.00 euro
       - calculate_lease_fee(25, 100000) returns 800.00 euro (200 euro discount for being under 30)
       - calculate_lease_fee(35, 150000) returns 1500.00 euro (50% higher salary = 50% higher lease)
       - calculate_lease_fee(28, 80000) returns 600.00 euro (80% of base lease minus 200 euro discount)
    """

@mcp.tool()
def calculate_lease_fee(age: int, salary: float) -> str:
    """
    Calculate monthly lease fee based on age and salary.
    
    Args:
        age: The person's age in years
        salary: The person's annual salary
        
    Returns:
        A formatted string with the calculated monthly lease fee
    """
    # Validate inputs
    if age < 0 or age > 120:
        return f"Error: Invalid age {age}. Age must be between 0 and 120."
    
    if salary < 0:
        return f"Error: Invalid salary {salary}. Salary must be a positive number."
    
    # Base calculation: 100,000 salary = 1000 euro per month
    # This means the rate is 0.01 (1%) of annual salary per month
    base_rate = 0.01
    monthly_lease = salary * base_rate
    
    # Apply age discount: if under 30, reduce by 200 euro
    age_discount = 0
    if age < 30:
        age_discount = 200
        monthly_lease -= age_discount
    
    # Ensure the lease fee doesn't go negative
    if monthly_lease < 0:
        monthly_lease = 0
    
    # Format the response
    if age_discount > 0:
        return f"Monthly lease fee: €{monthly_lease:.2f} (Base: €{salary * base_rate:.2f}, Age discount: -€{age_discount:.2f} for being under 30)"
    else:
        return f"Monthly lease fee: €{monthly_lease:.2f}"

if __name__ == "__main__":
    mcp.run(transport='stdio')
