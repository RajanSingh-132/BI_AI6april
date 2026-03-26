from fastapi import APIRouter, HTTPException
from models import ChatRequest
from utils.request_tracker import tracker
from services.conversationsSaver import get_chat_history
from services.ai_services import generate_ai_response
router = APIRouter()


@router.post("/chat")
async def chat(req: ChatRequest):

    try:
        tracker.api_hit()

        if not req.chat_history:
            raise HTTPException(status_code=400, detail="Chat history empty")

        user_message = req.chat_history[-1].content.strip()
        user_id = "user1"

        history = get_chat_history(user_id)

        # ✅ File upload case
        if "file uploaded" in user_message.lower():
            return {
                "answer": "File uploaded successfully ✅\n\n👉 Now ask your question from the dataset.",
                "kpis": [],
                "charts": []
            }

        # ✅ ONLY THIS
        result = generate_ai_response(user_id, user_message, history)

        return result

    except Exception as e:
        print("Chat API Error:", e)

        raise HTTPException(
            status_code=500,
            detail="Chat service unavailable"
        )