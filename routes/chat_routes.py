from fastapi import APIRouter
from prompt import format_response
from services.ai_services import generate_ai_response
from utils.request_tracker import tracker
from services.conversationsSaver import save_chat, get_chat_history   # ⭐ use your file

router = APIRouter()

tracker.api_hit()

@router.post("/chat")
async def chat(data: dict):

    user_message = data.get("message")
    user_id = "user1"   # later take from auth / frontend

    if not user_message:
        return {"response": "Message is required"}

    # ⭐ load history from DB instead of memory list
    history = get_chat_history(user_id)

    ai_text = generate_ai_response(user_id, user_message, history)
    ai_text = format_response(ai_text)

    # ⭐ SAVE CHAT
    save_chat(user_id, user_message, ai_text)

    return {"response": ai_text}