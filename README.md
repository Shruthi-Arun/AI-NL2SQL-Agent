# AI-Powered Natural Language to SQL Database Agent

## Project Summary
This project is an **AI-Powered Natural Language to SQL Database Agent** designed to convert natural-language questions into executable SQL queries for a PostgreSQL database. It integrates **dynamic schema and foreign-key discovery**, **complexity-based model routing**, **LLM-generated SQL**, **self-correction of errors**, and **logging of all interactions**.  

The agent allows users to interact with the database naturally without writing SQL themselves while leveraging large language models (LLMs) efficiently for different query complexities.  

The project aims to build a tool that lets users query a PostgreSQL database using natural language, removing the need for SQL knowledge. A locally hosted LLM (LLaMA 3 via Ollama) converts user input to SQL, making data access easier for non-technical users.  

Using a local LLM helps ensure **data privacy**, reduces reliance on external APIs, and improves **response time**. It also provides a practical foundation for exploring how language models can assist in **structured query generation**.


---

## Project Design

### 1. Architecture
The system is designed in modular layers:

1. **Input Layer**  
   - Receives natural-language questions via a CLI.  
   - Validates questions for minimum length and presence of letters.

2. **Database Layer**  
   - Connects to PostgreSQL using `psycopg2`.  
   - Dynamically fetches:
     - Table names  
     - Columns  
     - Foreign key relationships  
   - Ensures that the LLM generates queries aligned with the actual database schema.

3. **Query Complexity Detection**  
   - A lightweight keyword-based heuristic detects query difficulty:
     - **Level 1 (Simple):** list, show, count  
     - **Level 2 (Medium):** join, group by, sum  
     - **Level 3 (Hard):** window functions, ranking, CTEs  
   - Complexity determines which LLM model is invoked.

4. **LLM Layer**  
   - Uses **Ollama** to run LLMs.  
   - Different models are selected based on query complexity:
     - `llama3` for simple queries  
     - `llama3:instruct` for medium queries  
     - `llama3.1-70b` for hard queries  
   - Receives a structured prompt including:
     - Database schema  
     - Foreign key relationships  
     - User question  
     - Previous SQL errors (if any)

5. **SQL Extraction & Sanitization**  
   - Extracts SQL from LLM output using regex.  
   - Performs minor auto-corrections (e.g., `EXTRACT(YEAR)` fix, column renaming).

6. **Execution Layer**  
   - Executes SQL safely against PostgreSQL.  
   - Handles queries that return results or only perform modifications.  
   - Rolls back in case of errors.  

7. **Retry & Self-Correction**  
   - If SQL fails:
     - Sends the error back to the LLM.
     - Retries query generation up to **3 times**.
   - Helps ensure high success rates for more complex queries.

8. **Logging Layer**  
   - Records:
     - Timestamp
     - User question
     - SQL query
     - Error messages
     - Number of rows returned
     - LLM model used
     - LLM response time  
   - Logs stored in `agent_log.csv` for analysis.

---

## Development Process

1. **Requirement Gathering**  
   - Goal: Allow non-SQL users to query databases with natural language.  
   - Requirements:
     - Schema-aware query generation
     - Error correction
     - Complexity-based model routing
     - Logging

2. **Database Interaction**  
   - Used `psycopg2` to connect to PostgreSQL.  
   - Developed functions to fetch schema and foreign key relationships dynamically.  
   - Verified outputs against a sample `dvdrental` database.

3. **LLM Integration**  
   - Chose **Ollama** for local LLM execution.  
   - Tested multiple LLMs for different query complexities.  
   - Designed prompts to strictly enforce SQL output in ```sql``` fences.

4. **SQL Generation & Extraction**  
   - Implemented regex-based SQL extraction from LLM outputs.  
   - Added sanitization for common errors.

5. **Retry Mechanism**  
   - Developed a self-correcting system:
     - On SQL error, send feedback to LLM for a corrected query.  
     - Retries up to 3 times before failing.

6. **Complexity Detection**  
   - Created a keyword-based scoring system to detect simple, medium, and complex queries.  
   - Optimized for fast routing and minimal LLM resource usage.

7. **Logging & Monitoring**  
   - Built logging for both debugging and performance analysis.  
   - Recorded LLM response times to assess model efficiency.

8. **Interactive CLI**  
   - Implemented a command-line interface for real-time interaction.  
   - Users can type queries and see immediate results.

---

## Results

- **Functional Prototype**
  - Successfully generated valid SQL for:
    - Simple queries (e.g., list all customers)
    - Medium queries (e.g., join multiple tables with aggregation)
    - Complex queries (e.g., CTEs, ranking, window functions)
- **Self-Correction**
  - Error handling mechanism corrected ~80-90% of failed queries within 3 attempts.  
- **Dynamic Schema Awareness**
  - LLM never used columns/tables outside the database schema.  
- **Performance**
  - Lightweight queries executed quickly using small LLMs.  
  - Large queries routed to heavier LLMs maintained correctness without excessive runtime.  
- **Logging**
  - Enabled detailed post-analysis of LLM behavior, query complexity, and error patterns.

---

## Requirements

- Python 3.8+  
- PostgreSQL  
- [Ollama](https://ollama.com/)  
- LLaMA LLM models:
  - `llama3`
  - `llama3:instruct`
  - `llama3.1-70b`
- Python packages:
  ```bash
  pip install psycopg2

---

## How to Run

1. **Start PostgreSQL**  
   Ensure your PostgreSQL database is running and accessible.

2. **Install Ollama**  
   Follow instructions on [Ollama](https://ollama.com/) to install the CLI.

3. **Pull Required LLaMA Models**
   ```bash
   ollama pull llama3
   ollama pull llama3:instruct
   ollama pull llama3.1-70b

4. **Start Ollama to Test the Model**
   ```bash
   ollama run llama3 "Say hello!"

5. **Run the Python Script**
  ```bash
  python agent.py
  ```

6. **Ask Questions**  
Type SQL-related questions in natural language or type `exit` to quit.


