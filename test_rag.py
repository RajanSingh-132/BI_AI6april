from rag_engine import RAGEngine
# from models import Message


def run_tests():

    engine = RAGEngine()

    history =[]

    # -------------------------------
    # TEST 1: TOTAL DEAL VALUE
    # -------------------------------
    print("\n===== TEST 1: TOTAL DEAL VALUE =====")

    query1 = "what is profit in march?"
    print("Query:", query1)

    result1 = engine.process_query(
        query=query1,
        chat_history=history
    )

    print("Response:", result1)

if __name__ == "__main__":
    run_tests()