import asyncio
import os
import json
from textwrap import dedent
from typing import Optional, Dict, Any
import traceback
from agno.models.openai import OpenAIChat
from dotenv import load_dotenv
from agno.agent import Agent, RunResponse
from agno.models.groq import Groq
from agno.tools.mcp import MCPTools
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from agno.utils.log import logger
from llm_model import get_model

# --- Configuration ---

MARKDOWN=False,
SHOW_TOOL_CALLS=False,

load_dotenv()
MODEL_ID = os.getenv("MODEL_ID")
if not MODEL_ID:
        raise ValueError("GROQ_API_KEY environment variable is not set.")
MODEL_API_KEY = os.getenv("MODEL_API_KEY")
if not MODEL_API_KEY:
        raise ValueError("MODEL_API_KEY environment variable is not set.")

VISUALIZATION_TYPES = {
    "time_series": "Data that changes over time (sales trends, user growth)",
    "bar_chart": "Comparing categories or groups (sales by region, products by category)",
    "pie_chart": "Showing composition or proportion (market share, budget allocation)",
    "scatter_plot": "Relationship between two variables (price vs. rating, age vs. salary)",
    "heatmap": "Showing patterns or intensity across multiple dimensions (activity by hour/day)",
    "table": "Detailed individual records or aggregates requiring precise values",
    "gauge": "KPIs with target values (sales goals, customer satisfaction)",
    "funnel": "Sequential process steps with drop-offs (sales funnel, user journey)",
}

# --- Prompts ---

INSTRUCTIONS_DB_ANALYSIS_AND_SQL = dedent(
    """\
    You are an expert SQL data analyst and dashboard designer. Analyze the database schema and provide a comprehensive JSON report containing:

    1. **Database Domain:** Identify the most likely domain (e.g., sales, HR, inventory, travel) based on table and column names.
    2. **Key Metrics:** List the most important KPIs/metrics relevant to this domain.
    3. **Visualizations:** Recommend a suitable chart type for each metric and briefly explain why it's appropriate.
    4. **SQL Queries:** Generate SQL queries for each metric based on the database schema.
    5. **Dashboard Components:** Suggest which components (e.g., charts, tables, filters) to include in the dashboard.

    **PROCESS:**

    - Use the `get_schema` tool to retrieve the schema.
    - Analyze the table and column names to determine the domain.
    - Based on the domain identify relevant metrics and for each:
        - Name
        - Description
        - Visualization type (choose from: {visualization_types})
        - Visualization rationale
        - SQL query using correct table/column names
    - Return all output as a valid JSON in the following format do not add any extra text:

    ```json
    {{
      "domain": "Identified domain",
      "key_metrics": [
        {{
          "metric": "Metric Name",
          "description": "What this metric shows",
          "visualization_type": "e.g. bar_chart",
          "visualization_rationale": "Why this chart fits",
          "sql": "SELECT ... FROM ... WHERE ... GROUP BY ..."
        }}
      ],
      "dashboard_components": ["component1", "component2"]
    }}
    ```

    **GUIDELINES:**
    - Be concise and specific.
    - Ensure the SQL queries are valid, clean, and match the schema.
    - Only use the `get_schema` tool — no assumptions beyond that.
    - Output only the JSON. No extra commentary.

    **AVAILABLE TOOL:**
    - `get_schema`: Retrieves the database schema.
    """
).format(visualization_types=json.dumps(VISUALIZATION_TYPES))

INSTRUCTIONS_SQL_METRIC_DATA_JSON_ONLY = dedent(
    """\
    You are a senior data analyst.

    You will receive:
    - A JSON object containing multiple metrics, each with a name, description, visualization type, and an SQL query.
    - Access to a SQL database using the `read_query` tool.

    Your task is to:
    1. Execute each SQL query using the `read_query` tool.
    2. For each metric:
       - Capture the name, description, visualization type, and the result data.
    3. if result data is empty do nat add that item to the json.   
    4. Return a final JSON response containing all metrics with their corresponding result data.

    **OUTPUT FORMAT:**
    Return a single JSON object in the following structure:

    ```json
    {{
      "metrics": [
        {{
          "metric": "Metric name",
          "description": "Description of the metric",
          "visualization_type": "bar_chart | line_chart | pie_chart | table",
          "data": [
            {{ "column1": value, "column2": value }},
            ...
          ]
        }}
      ]
    }}
    ```

    **AVAILABLE TOOL:**
    - `read_query`: Executes a SELECT SQL query and returns results as a list of dictionaries.

    **IMPORTANT:**
    - Return only valid JSON.
    - Do not return HTML, explanations, or any other text.
    - If a query returns no data, return an empty list in `data`.
    """
)

INSTRUCTIONS_RENDER_DASHBOARD_FROM_DATA = dedent(
    """\
    You are a senior dashboard UI engineer.

    You will receive:
    - A JSON object containing an array of metrics.
    - Each metric includes: name, description, visualization type, and a list of data rows (already fetched from SQL).

    Your task is to:
    1. Render a complete, responsive HTML dashboard.
    2. For each metric:
       - Display the metric title and description.
       - If `visualization_type` is `bar_chart`, `line_chart`, or `pie_chart`, use Chart.js to render a responsive chart using the data.
       - If the data is not suitable for a chart (or if the type is `table`), render a styled HTML table.
    3. Style the page using **Tailwind CSS** for layout, responsiveness, and visual polish.
    4. Ensure each chart or table is inside a distinct card-like section.
    5. Make the layout mobile-friendly, elegant, and readable.

    **TOOLS TO USE:**
    - Use **Chart.js** (inline script tag from CDN).
    - Use **Tailwind CSS** (via CDN).

    **OUTPUT FORMAT:**
    Return only a valid, complete HTML document as a single string. No explanations or JSON — only the HTML.

    **IMPORTANT:**
    - Ensure the HTML is valid and renders cleanly in modern browsers.
    - All charts must be responsive.
    - Use intuitive colors and layout.
    - Do not include extra explanations or comments — just the HTML.
    """
)

# --- Helper Functions ---

def clean_json(data):
    """Removes extra text from the beginning of a JSON string and parses it."""
    start_index = data.find('{')
    if start_index == -1:
      start_index = data.find('[')
      if start_index == -1:
        raise ValueError("No JSON structure found in the string")
    
    cleaned_data = data[start_index:]
    return cleaned_data

def validate_dashboard_json(json_str: str) -> Dict[str, Any]:
    """Validates the structure of the dashboard JSON.

    Args:
        json_str: The JSON string to validate.

    Returns:
        The parsed JSON data if valid.

    Raises:
        ValueError: If the JSON is invalid or missing required keys.
    """
    try:
        data = json.loads(json_str)
        # Check for required keys
        if not all(key in data for key in ["domain", "key_metrics", "dashboard_components"]):
            raise ValueError("Missing required keys in JSON")
        # Check if key_metrics is a list
        if not isinstance(data["key_metrics"], list):
            raise ValueError("key_metrics must be a list")
        # Check if dashboard_components is a list
        if not isinstance(data["dashboard_components"], list):
            raise ValueError("dashboard_components must be a list")
        # Check if each metric has the correct keys
        for metric in data["key_metrics"]:
            if not all(key in metric for key in ["metric", "description", "visualization_type", "visualization_rationale", "sql"]):
                raise ValueError("Missing required keys in metric")
        return data
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON format: {e}")
    except ValueError as e:
        raise ValueError(f"Invalid JSON structure: {e}")


async def mcp_agent(session: ClientSession, instructions: str) -> Agent:
    """Creates and configures an agent that interacts with an SQL database via MCP.

    Args:
        session: The MCP client session.
        instructions: The instructions for the agent.

    Returns:
        The configured agent.

   
    """
    

    mcp_tools = MCPTools(session=session)
    await mcp_tools.initialize()
    logger.info(f"MODEL_ID: {MODEL_ID}")
    
        
    return Agent(
            model=get_model(MODEL_ID,MODEL_API_KEY),
            tools=[mcp_tools],
            instructions=instructions,
            markdown=MARKDOWN,
            show_tool_calls=SHOW_TOOL_CALLS,
        )

        


    


async def run_mcp_agent(message: str, instructions: str, max_retries: int = 3) -> RunResponse:
    """Runs an MCP agent with retry logic.

    Args:
        message: The message to send to the agent.
        instructions: The instructions for the agent.
        max_retries: The maximum number of retries.

    Returns:
        The agent's response.
    """
    retries = 0
    while retries < max_retries:
        try:
            server_params = StdioServerParameters(
                command="uvx",
                args=[
                    "mcp-sql-server",
                    "--db-host", os.getenv("DB_HOST"),
                    "--db-user", os.getenv("DB_USER"),
                    "--db-password", os.getenv("DB_PASSWORD"),
                    "--db-database", os.getenv("DB_NAME"),
                ],
            )

            async with stdio_client(server_params) as (read, write):
                async with ClientSession(read, write) as session:
                    agent = await mcp_agent(session=session, instructions=instructions)
                    response = await agent.arun(message)
                    return response

        except json.JSONDecodeError as e:
            logger.error(f"JSON decoding error: {e}\n{traceback.format_exc()}")
            return RunResponse(content=json.dumps({"error": "Invalid JSON format", "details": str(e)}))
        except ValueError as e:
            logger.error(f"Value error: {e}\n{traceback.format_exc()}")
            retries += 1
            if retries == max_retries:
                return RunResponse(content=json.dumps({"error": "Invalid JSON structure after multiple retries", "details": str(e)}))
            logger.warning(f"Retrying ({retries}/{max_retries}) after JSON structure error: {e}")
        except Exception as e:
            logger.error(f"Unexpected error: {e}\n{traceback.format_exc()}")
            return RunResponse(content=json.dumps({"error": "Unexpected error", "details": str(e)}))
    return RunResponse(content=json.dumps({"error": "Failed to get valid JSON after multiple retries"}))


# --- Main Functions ---

async def analyze_database(message: str, max_retries: int = 3) -> RunResponse:
    """Analyzes the database schema and returns a JSON report.

    Args:
        message: The message to send to the agent.
        max_retries: The maximum number of retries.

    Returns:
        The agent's response.
    """
    return await run_mcp_agent(
        message=message,
        instructions=INSTRUCTIONS_DB_ANALYSIS_AND_SQL,
        max_retries=max_retries,
    )


async def get_data_from_database(analysis_json: str, max_retries: int = 3) -> RunResponse:
    """Fetches data from the database based on the analysis JSON.

    Args:
        analysis_json: The JSON containing the SQL queries.
        max_retries: The maximum number of retries.

    Returns:
        The agent's response.
    """
    return await run_mcp_agent(
        message=analysis_json,
        instructions=INSTRUCTIONS_SQL_METRIC_DATA_JSON_ONLY,
        max_retries=max_retries,
    )


async def generate_html_dashboard(data_json: str) -> RunResponse:
    """Generates an HTML dashboard from the data JSON.

    Args:
        data_json: The JSON containing the data for the dashboard.
        

    Returns:
        The agent's response containing the HTML.
    """
    logger.info(f"Generating HTML dashboard from data: {data_json}")
    
    
        
    agent = Agent(
            model=get_model(MODEL_ID,MODEL_API_KEY),
            instructions=INSTRUCTIONS_RENDER_DASHBOARD_FROM_DATA,
            markdown=MARKDOWN,
            show_tool_calls=SHOW_TOOL_CALLS,
        )
    
    response = await agent.arun(data_json)
    return response


async def run_agent(message: str, max_retries: int = 3) -> RunResponse:
    """Main entry point for the dashboard agent.

    Args:
        message: The message to send to the agent.
        max_retries: The maximum number of retries for database analysis.

    Returns:
        The agent's response containing the HTML.

    Raises:
        ValueError: If any of the required database environment variables are not set.
    """
    required_vars = ["DB_HOST", "DB_USER", "DB_PASSWORD", "DB_NAME"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    if missing_vars:
        raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")

    analysis_response = await analyze_database(message, max_retries)
    analysis_json_str = analysis_response.content.strip()
    logger.info(f"Analysis JSON: {analysis_json_str}")
    # Remove code block markers if present
    if analysis_json_str.startswith("```json"):
        analysis_json_str = analysis_json_str[7:]
    if analysis_json_str.endswith("```"):
        analysis_json_str = analysis_json_str[:-3]
    cleaned_json_str = clean_json(analysis_json_str)
    try:
        validate_dashboard_json(cleaned_json_str)
    except ValueError as e:
        logger.error(f"Invalid JSON: {e}\n{analysis_json_str}")
        if "Invalid JSON structure after multiple retries" in str(e):
            return RunResponse(content=json.dumps({"error": "Failed to get valid JSON after multiple retries", "details": str(e)}))
        else:
            logger.warning("Retrying to get the right JSON")
            analysis_response = await analyze_database(message, max_retries)
            analysis_json_str = analysis_response.content.strip()
            if analysis_json_str.startswith("```json"):
                analysis_json_str = analysis_json_str[7:]
            if analysis_json_str.endswith("```"):
                analysis_json_str = analysis_json_str[:-3]
            try:
                cleaned_json_str = clean_json(analysis_json_str)
                validate_dashboard_json(cleaned_json_str)
            except ValueError as e:
                logger.error(f"Invalid JSON: {e}\n{analysis_json_str}")
                return RunResponse(content=json.dumps({"error": "Failed to get valid JSON after multiple retries", "details": str(e)}))

    data_response = await get_data_from_database(analysis_json_str)
    data_json_str = data_response.content.strip()
    logger.info(f"DATA JSON: {data_json_str}")
    if data_json_str.startswith("```json"):
        data_json_str = data_json_str[7:]
    if data_json_str.endswith("```"):
        data_json_str = data_json_str[:-3]

    html_response = await generate_html_dashboard(data_json_str)
    logger.info(f"HTML CODE: {html_response}")
    html_str = html_response.content.strip()
    if html_str.startswith("```html"):
        html_str = html_str[7:]
    if html_str.endswith("```"):
        html_str = html_str[:-3]
    return RunResponse(content=html_str)


# --- Example Usage ---

async def main():
    """Example usage of the dashboard agent."""
    try:
        response = await run_agent("Analyse my database and suggest a dashboard")
        logger.info(f"Agent Response: {response.content}")
    except ValueError as ve:
        logger.error(f"Configuration error: {ve}")
    except RuntimeError as re:
        logger.error(f"Runtime error: {re}")
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")


if __name__ == "__main__":
    asyncio.run(main())