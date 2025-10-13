import sqlite3
from llama_cpp import Llama

# Create a SQLite database and Messages table if it doesn't exist

conn = sqlite3.connect('backend/database.db')
cursor = conn.cursor()

cursor.execute("DROP TABLE IF EXISTS Personas")
cursor.execute("DROP TABLE IF EXISTS Sessions")
cursor.execute("DROP TABLE IF EXISTS Messages")
cursor.execute("DROP TABLE IF EXISTS Summaries")

cursor.execute("""
    CREATE TABLE IF NOT EXISTS Personas (
    persona_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    personality TEXT NOT NULL,
    tags TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
cursor.execute("""
    CREATE TABLE IF NOT EXISTS Sessions (
        session_id INTEGER PRIMARY KEY AUTOINCREMENT,
        creation_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP)
    """)
cursor.execute("""
    CREATE TABLE IF NOT EXISTS Messages (
        message_id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id INTEGER NOT NULL,
        role TEXT NOT NULL,
        content TEXT NOT NULL,
        date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        is_summarized INTEGER NOT NULL DEFAULT 0,
        FOREIGN KEY (session_id) REFERENCES Sessions(session_id)
        )
    """)
cursor.execute("""
    CREATE TABLE IF NOT EXISTS Summaries (
        summary_id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id INTEGER NOT NULL,
        summary_text TEXT NOT NULL,
        covers_from_message_id INTEGER NOT NULL,
        covers_to_message_id INTEGER NOT NULL,
        date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (session_id) REFERENCES Sessions(session_id),
        FOREIGN KEY (covers_from_message_id) REFERENCES Messages(message_id),
        FOREIGN KEY (covers_to_message_id) REFERENCES Messages(message_id)
        )
    """)
conn.commit()

cursor.execute("""INSERT INTO Personas (name, personality, tags) VALUES (
               "Sora", 
               "Eres un asistente útil, creativo, inteligente y muy amigable, que tiene conocimiento general de varias cosas y que tiene seguridad de lo que dice, pero también está abierto a cuestionamientos o dudas.", 
               "Respondes en español, asistente, amable, inteligente"
               )
               """)
cursor.execute("""INSERT INTO Personas (name, personality, tags) VALUES (
               "Hakurei", 
               "Eres un experto en anime y manga, con un conocimiento profundo sobre la serie Touhou Project. Tu tarea es responder preguntas relacionadas con esta serie de manera precisa y detallada, proporcionando información sobre personajes, tramas, juegos y cualquier otro aspecto relevante de Touhou Project.", 
               "Respondes en español, anime, manga, Touhou Project, experto"
               )
               """)
conn.commit()

persona = 2 # Change this value to switch personas
cursor.execute("SELECT name, personality, tags FROM Personas WHERE persona_id = ?" , (persona,))
personality = cursor.fetchone()

# Load your GGUF model file
llm = Llama(
    model_path="D:/proietkoz/Models/Llama-3.2-3B-Instruct-Q4_K_M.gguf",
    n_ctx=2048,
    n_threads=6,
    n_gpu_layers=-1,
    n_batch=512
)

def summarize_conversation():
    sql_command = "SELECT message_id, content, role, is_summarized FROM Messages WHERE is_summarized = 0 ORDER BY date ASC LIMIT 10"
    cursor.execute(sql_command)
    history = cursor.fetchall()

    min_message_id = history[0][0]
    max_message_id = history[-1][0]

    for mess in history:
        content = mess[1]
        role = mess[2]

        if role == "user":
            summarize += f"User: {content}\n"
        elif role == "assistant":
            summarize += f"Assistant: {content}\n"
            
        summarized_messages.append(mess[0])

    placeholders = ','.join('?' * len(summarized_messages))
    sql_command = f"UPDATE Messages SET is_summarized = 1 WHERE message_id IN ({placeholders})"
    cursor.execute(sql_command, summarized_messages)
    conn.commit()

    summarize_prompt = f"""<|start_header_id|>system<|end_header_id|>
    Cutting Knowledge Date: December 2023
    Today Date: 13 Oct 2025

    Eres un asistente que resume conversaciones. Extrae SOLO hechos relevantes (preferencias, decisiones, nombres, fechas) en 3 viñetas cortas, máximo 120 caracteres en total.
    <|eot_id|><|start_header_id|>user<|end_header_id|>
    {summarize}
    <|eot_id|><|start_header_id|>assistant<|end_header_id|>"""

    summ_output = llm(summarize_prompt, max_tokens=120, temperature=0.7, echo=False)
    summarized_conversation = summ_output["choices"][0]["text"].strip()
    sql_command = "INSERT INTO Summaries (session_id, summary_text, covers_from_message_id, covers_to_message_id) VALUES (?, ?, ?, ?)"
    cursor.execute(sql_command, (session_id, summarized_conversation, min_message_id, max_message_id))
    conn.commit()
    summarize = "Resumen de la conversación hasta ahora:\n"
    summarized_messages = []

def short_memory(history):
    short_history = ""
    for mess in history:
        content = mess[0] if mess[2] == 0 else ""
        role = mess[1] if mess[2] == 0 else ""

        if role == "user":
            short_history += f"<|start_header_id|>user<|end_header_id|>\n\n{content}<|eot_id|>"
        elif role == "assistant":
            short_history += f"<|start_header_id|>assistant<|end_header_id|>\n\n{content}<|eot_id|>"
    
    return short_history

# Start a new session
cursor.execute("INSERT INTO Sessions DEFAULT VALUES")
conn.commit()

sql_command = "SELECT session_id FROM Sessions ORDER BY creation_date DESC LIMIT 1"
cursor.execute(sql_command)
session_id = cursor.fetchone()[0]

user_role = "user"
assistant_role = "assistant"

summarize = "Resumen de la conversación hasta ahora:\n"
summarized_messages = []

while True:
    message = input("Tú: ")

    # Insert a user message into the Messages table
    sql_command = "INSERT INTO Messages (session_id, role, content) VALUES (?, ?, ?)"
    cursor.execute(sql_command, (session_id, user_role, message))
    conn.commit()

    sql_command = "SELECT content, role, is_summarized FROM Messages ORDER BY date ASC LIMIT 20"

    cursor.execute(sql_command)
    history = cursor.fetchall()

    formatted_history = short_memory(history)

    # Check if there are 20 unsummarized messages to trigger summarization
    cursor.execute("SELECT COUNT(*) FROM Messages WHERE is_summarized = 0")
    unsummarized_count = cursor.fetchone()[0]
    if unsummarized_count >= 20:
        summarize_conversation()

    # Retrieve the latest summary
    sql_command = "SELECT summary_text FROM Summaries ORDER BY date DESC LIMIT 1"
    cursor.execute(sql_command)
    summary = cursor.fetchone()

    system_prompt = f"""<|start_header_id|>system<|end_header_id|>

        Cutting Knowledge Date: December 2023
        Today Date: 13 Oct 2025

        ---Persona y Tarea---
        Nombre: {personality[0]}
        Personalidad: {personality[1]}
        Tags: {personality[2]}

        ---Resumen de la conversación hasta ahora---
        {summary[0] if summary else "No hay resumen disponible."}
        <|eot_id|>
        """
    
    user_part = f"""<|start_header_id|>user<|end_header_id|>
        {message}
        <|eot_id|><|start_header_id|>assistant<|end_header_id|>"""

    prompt = system_prompt + formatted_history + user_part
    output = llm(prompt, max_tokens=512, temperature=0.7, echo=False)
    
    response = output["choices"][0]["text"].strip()
    print("\nRespuesta de la IA:\n", response)

    # Insert Assistant message into the Messages table
    sql_command = "INSERT INTO Messages (session_id, role, content) VALUES (?, ?, ?)"
    cursor.execute(sql_command, (session_id, assistant_role, response))
    conn.commit()