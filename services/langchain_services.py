from langchain.memory import ConversationBufferMemory

# ================================
# 🔥 GLOBAL MEMORY STORE (per user)
# ================================

memory_store = {}


def get_memory(user_id: str):

    if user_id not in memory_store:
        memory_store[user_id] = ConversationBufferMemory(
            memory_key="chat_history",
            return_messages=True
        )

    return memory_store[user_id]


# ================================
# 🔥 FORMAT MEMORY → TEXT
# ================================

def format_memory(memory, limit=5):

    chat_history = memory.load_memory_variables({}).get("chat_history", [])

    # 🔥 limit last N messages (important)
    chat_history = chat_history[-limit:]

    formatted = ""

    for msg in chat_history:
        if msg.type == "human":
            formatted += f"User: {msg.content}\n"
        elif msg.type == "ai":
            formatted += f"AI: {msg.content}\n"

    return formatted.strip()


# ================================
# 🔥 SAVE TO MEMORY
# ================================

def save_to_memory(memory, user_input, ai_output):

    if not user_input or not ai_output:
        return

    memory.save_context(
        {"input": user_input},
        {"output": ai_output}
    )