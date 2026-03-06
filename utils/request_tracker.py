class RequestTracker:
    def __init__(self):
        self.total_api_calls = 0
        self.total_gemini_calls = 0

    def api_hit(self):
        self.total_api_calls += 1
        print(f"🔥 API Calls: {self.total_api_calls}")

    def gemini_hit(self):
        self.total_gemini_calls += 1
        print(f"🚀 Gemini Calls: {self.total_gemini_calls}")


# global instance
tracker = RequestTracker()