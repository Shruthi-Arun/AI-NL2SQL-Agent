import subprocess
import psycopg2
import re
import datetime
import os
import time

# -----------------------------
# -------Input validation------
# -----------------------------


def is_valid_input(question):
    return bool(question.strip()) and re.search(r"[A-Za-z]", question) and len(question.strip()) >= 3

# -----------------------------
# -------Database setup--------
# -----------------------------

def init_db():
    conn = psycopg2.connect(
        dbname="dvdrental",
        user="postgres",
        password="password",
        host="localhost"
    )
    cur = conn.cursor()
    return conn, cur

# -----------------------------
# -------Execute SQL safely----
# -----------------------------

def execute_query(cur, conn, sql):
    try:
        cur.execute(sql)
        try:
            results = cur.fetchall()
        except psycopg2.ProgrammingError:
            results = []
        conn.commit()
        return results, None
    except Exception as e:
        conn.rollback()
        return None, str(e)

# -----------------------------
# -------Fetch schema----------
# -----------------------------

def fetch_schema(cur):
    cur.execute("""
        SELECT table_name, column_name
        FROM information_schema.columns
        WHERE table_schema='public'
        ORDER BY table_name, ordinal_position;
    """)
    rows = cur.fetchall()
    schema_dict = {}
    for table, column in rows:
        schema_dict.setdefault(table, []).append(column)
    return "\n".join([f"TABLE: {t}\nCOLUMNS: {', '.join(cols)}\n" for t, cols in schema_dict.items()])

# -----------------------------
# -------Fetch foreign key 
# -------relationships dynamically
# -----------------------------


def fetch_relationships(cur):
    cur.execute("""
        SELECT
            tc.table_name AS source_table,
            kcu.column_name AS source_column,
            ccu.table_name AS target_table,
            ccu.column_name AS target_column
        FROM 
            information_schema.table_constraints AS tc 
        JOIN information_schema.key_column_usage AS kcu
            ON tc.constraint_name = kcu.constraint_name
            AND tc.table_schema = kcu.table_schema
        JOIN information_schema.constraint_column_usage AS ccu
            ON ccu.constraint_name = tc.constraint_name
            AND ccu.table_schema = tc.table_schema
        WHERE tc.constraint_type = 'FOREIGN KEY'
        ORDER BY tc.table_name, kcu.column_name;
    """)
    rows = cur.fetchall()
    return "Relationships / Foreign Keys:\n" + "".join(
        f"- {src}.{src_col} -> {tgt}.{tgt_col}\n" for src, src_col, tgt, tgt_col in rows
    )

# -----------------------------
# -------Extract SQL 
# -------from LLM output
# -----------------------------

def extract_sql(text):
    if not text:
        return None
    text = text.replace("``` sql", "```sql").replace("``` SQL", "```sql").replace("``` Sql", "```sql")
    match = re.search(r"```sql\s*(.*?)```", text, re.DOTALL | re.IGNORECASE)
    if match:
        sql = match.group(1).strip()
    else:
        sql = text.replace("```", "").replace("`", "").strip()
    sql = re.sub(r'^\s*sql\s*\n', '', sql, flags=re.IGNORECASE | re.MULTILINE)
    if sql.lower().startswith("sql "):
        sql = sql[4:].strip()
    return sql.strip()

# -----------------------------
# -------Logging---------------
# -----------------------------
def log_interaction(question, sql_query, results, error_message, model_used, llm_time):
    log_file = "agent_log.csv"
    header_needed = not os.path.exists(log_file)
    with open(log_file, "a") as f:
        if header_needed:
            f.write("timestamp,question,sql_query,error,rows_returned,model_used,llm_time\n")
        timestamp = datetime.datetime.now().isoformat()
        rows_count = len(results) if results else 0
        sql_safe = sql_query.replace("\n", " ").replace(",", ";") if sql_query else ""
        error_safe = error_message.replace("\n", " ").replace(",", ";") if error_message else ""
        f.write(f"{timestamp},{question},{sql_safe},{error_safe},{rows_count},{model_used},{llm_time:.2f}\n")

# -----------------------------
# -------Query complexity detection
# -------3 LEVELS (simple / medium / hard)
# -----------------------------

def detect_complexity(question):
    q = question.lower()

    level1_keywords = ["list", "show", "find all", "count", "simple", "basic"]
    level2_keywords = ["join", "group by", "sum", "average", "per", "between", "filter on", "nested"]
    level3_keywords = ["rank", "window", "partition", "recursive", "cte", "top", "advanced", "correlated"]

    score = 0
    for kw in level2_keywords:
        if kw in q:
            score += 1
    for kw in level3_keywords:
        if kw in q:
            score += 2

    if score == 0:
        return 1   # simple
    if score <= 3:
        return 2   # medium
    return 3       # hard

# -----------------------------
# -------Run LLM with 
# -------3-tier routing
# -----------------------------

def run_ollama_with_routing(prompt, question):
    level = detect_complexity(question)

    if level == 1:
        model = "llama3"
    elif level == 2:
        model = "llama3:instruct"
    else:
        model = "llama3.1-70b"   

    print(f"→ Query classified as LEVEL {level} → Routing to model: {model}")

    start_time = time.time()

    try:
        result = subprocess.run(
            ["ollama", "run", model, prompt],
            capture_output=True, text=True, encoding="utf-8", check=True
        )
        llm_time = time.time() - start_time
        return result.stdout.strip(), model, llm_time
    except subprocess.CalledProcessError as e:
        llm_time = time.time() - start_time
        print("Ollama error:", e)
        return None, model, llm_time

# -----------------------------
# -------Auto-fix 
# -------common SQL mistakes
# -----------------------------

def sanitize_sql(sql):
    if not sql:
        return sql

    sql = re.sub(r'EXTRACT\(YEAR FROM (\w+)\)', r'\1', sql, flags=re.IGNORECASE)
    sql = re.sub(r'\byr\b', 'rental_year', sql)
    return sql

# -----------------------------
# -------SQL generator---------
# -----------------------------

def agent_generate_sql(question, schema_text, cur, prev_error=None):
    relationships = fetch_relationships(cur)

    prompt = f"""
You are an autonomous PostgreSQL SQL-generation agent.

RULES:
- Return ONLY SQL inside ```sql``` ... ```
- Use ONLY tables/columns that appear in the schema
- Use JOINs based on the foreign key relationships provided
- If previous SQL failed, FIX it
- Use CTEs and window functions for advanced queries

SCHEMA:
{schema_text}

{relationships}

USER QUESTION:
{question}

PREVIOUS ERROR (if any):
{prev_error}

Return only ONE SQL query inside ```sql``` fences.
"""

    raw, model_used, llm_time = run_ollama_with_routing(prompt, question)
    sql = extract_sql(raw)
    sql = sanitize_sql(sql)
    return sql, model_used, llm_time

# -----------------------------
# -------Main CLI loop---------
# -----------------------------

if __name__ == "__main__":
    print("AI SQL Agent (3-level routing, dynamic schema, dynamic FK mapping) running...")

    conn, cur = init_db()
    schema_text = fetch_schema(cur)

    try:
        while True:
            question = input("\nAsk a question (or 'exit'): ").strip()
            if question.lower() == "exit":
                break
            if not is_valid_input(question):
                print("Invalid input.")
                continue

            attempts = 0
            max_attempts = 3
            error_message = None

            while attempts < max_attempts:
                sql_query, model_used, llm_time = agent_generate_sql(
                    question, schema_text, cur, error_message
                )

                if not sql_query:
                    print("LLM failed to produce SQL.")
                    break

                sql_query = sql_query.replace("```", "").replace("`", "").strip()
                sql_query = re.sub(r'^\s*sql\s*\n', '', sql_query, flags=re.IGNORECASE)

                print(f"\nAttempt {attempts+1} SQL (Model: {model_used}):\n{sql_query}")

                results, error_message = execute_query(cur, conn, sql_query)

                log_interaction(question, sql_query, results, error_message, model_used, llm_time)

                if error_message:
                    print(f"Database error: {error_message}")
                    attempts += 1
                    if attempts < max_attempts:
                        print("\nRetrying with auto-correction...\n")
                    continue
                else:
                    print("\nQuery executed successfully!")
                    print("Results:", results)
                    break

            if attempts == max_attempts and error_message:
                print("Failed after 3 attempts.\nLast error:", error_message)

    finally:
        cur.close()
        conn.close()
