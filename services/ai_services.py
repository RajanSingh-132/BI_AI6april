import os
import time
from dotenv import load_dotenv
from google import genai
from prompt import build_prompt
from utils.request_tracker import tracker
# ✅ Load env
load_dotenv()

API_KEY = os.getenv("GEMINI_API_KEY")
if not API_KEY:
    raise ValueError("GEMINI_API_KEY missing")

# ✅ New Gemini client
client = genai.Client(api_key=API_KEY)

tracker.gemini_hit()
def generate_ai_response(user_id: str, message: str, history=None) -> str:
    """
    Generate AI response using Gemini with retry + quota protection
    """

    prompt = build_prompt(message, history)

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",   # ✅ more free quota
            contents=prompt
        )

        return getattr(response, "text", "No response")

    except Exception as e:
        error_text = str(e)
        print("AI Error:", error_text)

        # ✅ Handle quota error with retry
        if "429" in error_text or "RESOURCE_EXHAUSTED" in error_text:
            try:
                time.sleep(8)  # Gemini suggested retry delay

                response = client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=prompt
                )
                return getattr(response, "text", "No response")

            except Exception as retry_error:
                print("Retry failed:", retry_error)
                return "AI quota exceeded. Please try again later."

        return "AI service is temporarily unavailable."