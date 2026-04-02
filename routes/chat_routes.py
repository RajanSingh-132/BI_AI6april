from fastapi import APIRouter, HTTPException, Request
from models import ChatRequest
from utils.request_tracker import tracker
from services.conversationsSaver import get_chat_history
from services.ai_services import generate_ai_response
router = APIRouter()


def _is_upload_event_message(message: str) -> bool:
    normalized = (message or "").strip().lower()
    return (
        normalized.startswith("file uploaded")
        or "file uploaded successfully" in normalized
        or normalized.startswith("uploaded file:")
    )


@router.post("/chat")
async def chat(req: ChatRequest, request: Request):

    try:
        tracker.api_hit()

        if not req.chat_history:
            raise HTTPException(status_code=400, detail="Chat history empty")

        user_message = req.chat_history[-1].content.strip()
        user_id = "user1"

        history = get_chat_history(user_id)

        # Treat upload acknowledgements as system events, not analytics queries.
        if _is_upload_event_message(user_message):
            return {
                "answer": "",
                "answer_html": "",
                "kpis": [],
                "charts": [],
                "type": "system",
                "skip_analytics": True,
                "skip_history": True,
                "is_upload_event": True,
                "datasets_used": req.active_datasets or getattr(request.app.state, 'ACTIVE_DATASETS', []),
                "comparison_mode": False,
                "ai_intelligence_analysis": []
            }

        # ✅ Extract active datasets from request or fallback to app state
        active_datasets = req.active_datasets or getattr(request.app.state, 'ACTIVE_DATASETS', [])
        
        # ✅ AUTO-DETECT: Comparison mode based on query keywords + multiple datasets
        comparison_keywords = ['compare', 'vs', 'versus', 'between', 'differences', 'contrast', 'which one']
        query_lower = user_message.lower()
        has_comparison_keyword = any(kw in query_lower for kw in comparison_keywords)
        auto_comparison_mode = has_comparison_keyword and len(active_datasets) > 1
        
        # ✅ Use auto-detected mode (can still be overridden by explicit request flag)
        comparison_mode = req.comparison_mode if req.comparison_mode is not None else auto_comparison_mode
        
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
