
from fastapi.testclient import TestClient
from main import app  # 🔥 make sure this matches your main file name

client = TestClient(app)


# =========================
# ✅ TEST: Chat API
# =========================
def test_chat_api_success():
    payload = {
        "chat_history": [
            {
                "role": "human",
                "content": "What is total sales?",
                "type": "text"
            }
        ]
    }

    response = client.post("/chat", json=payload)

    print("Chat Response:", response.json())

    assert response.status_code == 200
    assert "answer" in response.json()


# =========================
# ❌ TEST: Chat API Empty Input
# =========================
def test_chat_api_empty():
    payload = {
        "chat_history": []
    }

    response = client.post("/api/chat", json=payload)

    print("Empty Chat Response:", response.json())

    assert response.status_code in [200, 400, 422]


# =========================
# ✅ TEST: Upload JSON API
# =========================
def test_upload_json_success():
    payload = {
        "data": [
            {"name": "Product A", "sales": 100},
            {"name": "Product B", "sales": 200}
        ]
    }

    response = client.post("/upload-json", json=payload)

    print("Upload Response:", response.json())

    assert response.status_code == 200


# =========================
# ❌ TEST: Invalid Route
# =========================
def test_invalid_route():
    response = client.post("/chat")

    assert response.status_code == 404