import asyncio
import os
from dotenv import load_dotenv
from textwrap import dedent
from agno.agent import Agent, RunResponse
from agno.models.groq import Groq
from agno.models.openai import OpenAIChat
from agno.tools.mcp import MCPTools
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from agno.utils.log import logger
from typing import Optional
from llm_model import get_model




INSTRUCTIONS = dedent(
    """\
    You are an intelligent SQL assistant with access to a database through the MCP tool.

    Your job is to:
    1. Understand the user’s question or request related to data.
    2. Use the `get_schema` tool to retrieve the structure of the database, if needed.
    3. Generate a valid SQL `SELECT` query using the correct table and column names.
    4. Use the `read_query` tool to run your query and retrieve the results.
    5. Analyze the results and respond with a **clear, natural language summary** of the data.
       - This response should be simple, accurate, and easy to understand.
       - Focus on key insights, trends, counts, comparisons, or highlights.
       - Include numbers or observations, not just restatements.
       - Avoid technical jargon or raw data unless specifically requested.

    Constraints:
    - Only use SELECT queries.
    - Do not perform INSERT, UPDATE, DELETE, or any modification operations.
    - Do not return raw SQL or result tables unless explicitly asked by the user.
    - Always return a human-friendly explanation, even if the result is empty or zero.

    Tools you can use:
    - `get_schema`: Retrieves the full schema of the database.
    - `read_query`: Executes a SELECT query and returns the result as a list of dictionaries.

    Examples of user queries:
    - "How many new users signed up last week?"
    - "Which products generated the most revenue this year?"
    - "Show me the monthly breakdown of orders in 2023."
    - "What are the top 5 countries by number of customers?"

    You MUST respond with:
    - A well-written, friendly summary of the result.
    - You may include a short chart description if applicable (e.g., “This could be shown as a bar chart.”).
    - Nothing else — no explanations of how you got the result.

    Begin by reading the user's question and proceed accordingly.
    """
)

# Load environment variables from .env file
load_dotenv()
MODEL_ID = os.getenv("MODEL_ID")
if not MODEL_ID:
        raise ValueError("GROQ_API_KEY environment variable is not set.")
MODEL_API_KEY = os.getenv("MODEL_API_KEY")
if not MODEL_API_KEY:
        raise ValueError("MODEL_API_KEY environment variable is not set.")

# Default model ID if not specified in environment variables
DEFAULT_MODEL_ID = "llama-3.3-70b-versatile"


async def db_connection_agent(session: ClientSession, model_id: Optional[str] = None) -> Agent:
    """
    Creates and configures an agent that interacts with an SQL database via MCP.

    Args:
        session (ClientSession): The MCP client session.
        model_id (Optional[str]): The ID of the language model to use. Defaults to DEFAULT_MODEL_ID.

    Returns:
        Agent: The configured agent.

    """
    
    # Initialize the MCP toolkit
    mcp_tools = MCPTools(session=session)
    await mcp_tools.initialize()
    
    
    # Create and return the configured agent
    return Agent(
        model=get_model(model_id,MODEL_API_KEY),
        tools=[mcp_tools],
        instructions=INSTRUCTIONS,
        markdown=True,
        show_tool_calls=True,
    )
    
   
   
    
    


async def run_agent(message: str, model_id: Optional[str] = None) -> RunResponse:
    """
    Runs the agent with the given message and returns the response.

    Args:
        message (str): The message to send to the agent.
        model_id (Optional[str]): The ID of the language model to use. Defaults to DEFAULT_MODEL_ID.

    Returns:
        RunResponse: The agent's response.

    Raises:
        ValueError: If any of the required database environment variables are not set.
        RuntimeError: If there is an error connecting to the MCP server.
    """
    # Check for required database environment variables
    required_vars = ["DB_HOST", "DB_USER", "DB_PASSWORD", "DB_NAME"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    if missing_vars:
        raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")

    # Configure MCP server parameters
    server_params = StdioServerParameters(
        command="uvx",
        args=[
            "mcp-sql-server",
            "--db-host",
            os.getenv("DB_HOST"),
            "--db-user",
            os.getenv("DB_USER"),
            "--db-password",
            os.getenv("DB_PASSWORD"),
            "--db-database",
            os.getenv("DB_NAME"),
        ],
    )

    # Connect to the MCP server and run the agent
    try:
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                agent = await db_connection_agent(session, model_id)
                response = await agent.arun(message)
                return response
    except Exception as e:
        raise RuntimeError(f"Error connecting to MCP server or running agent: {e}") from e


async def main():
    """
    Example usage of the agent.
    """
    try:
        # Run the agent with a sample query
        response = await run_agent("get a list of all employees")
        logger.info(f"Agent Response: {response.content}")
    except ValueError as ve:
        logger.error(f"Configuration error: {ve}")
    except RuntimeError as re:
        logger.error(f"Runtime error: {re}")
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")


if __name__ == "__main__":
    asyncio.run(main())