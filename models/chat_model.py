from datetime import datetime
from app.database.mongo import chat_collection


def save_chat(user_id: str, message: str, response: str):

    now = datetime.utcnow()

    chat_data = {
        "user_id": user_id,
        "message": message,
        "response": response,

        # ✅ Separate fields
        "date": now.strftime("%Y-%m-%d"),
        "time": now.strftime("%H:%M:%S"),

        # ✅ Full timestamp (recommended for sorting)
        "created_at": now
    }

    chat_collection.insert_one(chat_data)


def get_chat_history(user_id: str):

    chats = chat_collection.find({"user_id": user_id}).sort("created_at", 1)

    history = []

    for chat in chats:
        history.append({
            "role": "user",
            "content": chat["message"]
        })
        history.append({
            "role": "assistant",
            "content": chat["response"]
        })

    return history