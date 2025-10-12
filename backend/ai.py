import sqlite3
from llama_cpp import Llama

# Create a SQLite database and Messages table if it doesn't exist

conn = sqlite3.connect('backend/database.db')
cursor = conn.cursor()

cursor.execute("""
    CREATE TABLE IF NOT EXISTS Messages (
        message_id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id INTEGER NOT NULL,
        role TEXT NOT NULL,
        content TEXT NOT NULL,
        date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
conn.commit()

# Load your GGUF model file
llm = Llama(
    model_path="D:/proietkoz/Models/Llama-3.2-3B-Instruct-Q4_K_M.gguf",
    n_ctx=2048,
    n_threads=6,
    n_gpu_layers=-1,
    n_batch=512
)

user_role = "user"
assistant_role = "assistant"

while True:
    message = input("Tú: ")

    # Insert a user message into the Messages table
    sql_command = "INSERT INTO Messages (session_id, role, content) VALUES (?, ?, ?)"
    cursor.execute(sql_command, (1, user_role, message))
    conn.commit()

    sql_command = "SELECT content, role FROM Messages ORDER BY date ASC"

    cursor.execute(sql_command)
    history = cursor.fetchall()

    formatted_history = ""
    for mess in history:
        content = mess[0]
        role = mess[1]

        if role == "user":
            formatted_history += f"<|start_header_id|>user<|end_header_id|>\n\n{content}<|eot_id|>"
        elif role == "assistant":
            formatted_history += f"<|start_header_id|>assistant<|end_header_id|>\n\n{content}<|eot_id|>"

    system_prompt = f"""<|start_header_id|>system<|end_header_id|>

        Cutting Knowledge Date: December 2023
        Today Date: 09 Oct 2025

        Eres un experto en anime y manga, con un conocimiento profundo sobre la serie Touhou Project. Tu tarea es responder preguntas relacionadas con esta serie de manera precisa y detallada, proporcionando información sobre personajes, tramas, juegos y cualquier otro aspecto relevante de Touhou Project.
        <|eot_id|>
        """
    
    user_part = f"""<|start_header_id|>user<|end_header_id|>
        {message}
        <|eot_id|><|start_header_id|>assistant<|end_header_id|>"""

    prompt = system_prompt + formatted_history + user_part
    output = llm(prompt, max_tokens=2048, temperature=0.7, echo=False)
    
    response = output["choices"][0]["text"].strip()
    print("\nRespuesta de la IA:\n", response)

    # Insert Assistant message into the Messages table
    sql_command = "INSERT INTO Messages (session_id, role, content) VALUES (?, ?, ?)"
    cursor.execute(sql_command, (1, assistant_role, response))
    conn.commit()