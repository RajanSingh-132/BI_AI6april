from datetime import datetime
from database.mongo import chat_collection


def save_chat(user_id: str, message: str, response: str):

    now = datetime.utcnow()

    chat_data = {
        "user_id": user_id,
        "message": message,
        "response": response,
        "created_at": now
    }

    chat_collection.insert_one(chat_data)


def get_chat_history(user_id: str):

    chats = (
        chat_collection
        .find({"user_id": user_id})
        .sort("created_at", 1)
        .limit(20)
    )

    history = []

    for chat in chats:

        history.append({
            "role": "human",
            "content": chat["message"]
        })

        history.append({
            "role": "ai",
            "content": chat["response"]
        })

    return history