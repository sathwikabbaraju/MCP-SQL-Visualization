# MCP SQL Visualization

An AI-powered system that transforms SQL databases into interactive dashboards using natural language queries.

---

## 📌 Project Overview

**MCP SQL Visualization** removes the need for SQL expertise when analyzing data. Users can ask questions in plain English, and the system will generate SQL queries, execute them, and visualize the results automatically. The tool is designed for secure, read-only access to your database and leverages large language models (LLMs) for intelligent data interpretation.

---

## ✨ Features

- **Natural Language Interface:**  
  Ask questions in plain English; the system generates and runs SQL queries for you.

- **Automated Dashboards:**  
  Instantly create visualizations and dashboards from your data.

- **Secure Database Access:**  
  All operations are read-only, with schema-level permissions and SQL injection protection.

- **Multi-Database Support:**  
  Compatible with MySQL and PostgreSQL.

- **Export Options:**  
  Download dashboards as HTML or PDF.

---

## 🛠️ Architecture

graph TD
A[Streamlit UI] --> B[LLM Agent]
B --> C[MCP Server]
C --> D[SQL Database]
D --> C
C --> B
B --> A


**Components:**
- **Streamlit Frontend:** User interface for chat and dashboard interaction.
- **LLM Agent:** Converts natural language to SQL and interprets results.
- **MCP Server:** Manages query validation, database connection, and security.
- **Database:** Your SQL data source (MySQL/PostgreSQL).

---

## 🚀 Installation

### Prerequisites

- Python 3.9+
- MySQL or PostgreSQL database
- LLM API Key (Anthropic/OpenAI/Groq)

### Steps

1. **Clone the repository:**
    ```
    git clone https://github.com/yourusername/mcp-sql-visualization.git
    cd mcp-sql-visualization
    ```

2. **Set up a virtual environment:**
    ```
    python -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate
    ```

3. **Install dependencies:**
    ```
    pip install -r requirements.txt
    ```

4. **Configure environment variables:**
    Create a `.env` file in the project root with the following content:
    ```
    DB_HOST=your_database_host
    DB_USER=readonly_user
    DB_PASSWORD=secure_password
    DB_NAME=your_database
    LLM_API_KEY=your_api_key
    MODEL_ID=claude-3-opus-20240229
    ```

5. **Start the backend server:**
    ```
    uvicorn mcp_server:app --reload --port 8000
    ```

6. **Launch the Streamlit UI:**
    ```
    streamlit run app.py
    ```

---

## 🖥️ Usage

1. **Ask a Question:**  
   Type a question in plain English in the chat interface.  
   _Example:_  
What were our top 5 selling products last quarter?


2. **Generate a Dashboard:**  
Request a visualization or report.  
_Example:_  
Show monthly sales trends by region with key metrics.


3. **Export Results:**  
Download the generated dashboard as HTML or PDF for sharing.

---

## 🔒 Security

- **Read-Only Database Access:** Only SELECT queries are permitted.
- **Schema Validation:** Queries are checked against allowed tables and columns.
- **SQL Injection Protection:** All inputs are sanitized and parameterized.

**Example Query Validation:**
def validate_query(query: str):
if not query.strip().upper().startswith("SELECT"):
raise Exception("Only SELECT queries are allowed.")


---

## 🤝 Contributing

1. Fork the repository.
2. Create a new branch:  
   `git checkout -b feature/your-feature`
3. Commit your changes:  
   `git commit -m 'Add your feature'`
4. Push to the branch:  
   `git push origin feature/your-feature`
5. Open a Pull Request.

---

## 🙏 Acknowledgements
- Agno AI Agent Framework
- Streamlit

---

Happy Visualizing! 🚀
