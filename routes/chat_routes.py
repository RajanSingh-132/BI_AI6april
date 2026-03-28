from fastapi import APIRouter, HTTPException, Request
from models import ChatRequest
from utils.request_tracker import tracker
from services.conversationsSaver import get_chat_history
from services.ai_services import generate_ai_response
router = APIRouter()


@router.post("/chat")
async def chat(req: ChatRequest, request: Request):

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

        # ✅ Extract active datasets from request or fallback to app state
        active_datasets = req.active_datasets or getattr(request.app.state, 'ACTIVE_DATASETS', [])
        comparison_mode = req.comparison_mode or False
        
        # ✅ ONLY THIS - pass request so ai_services can access app state and multiple datasets
        result = generate_ai_response(
            user_id, 
            user_message, 
            history, 
            request,
            active_datasets=active_datasets,
            comparison_mode=comparison_mode
        )

        return result

    except Exception as e:
        print("Chat API Error:", e)

        raise HTTPException(
            status_code=500,
            detail="Chat service unavailable"
        )