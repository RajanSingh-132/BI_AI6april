import os
from dotenv import load_dotenv

load_dotenv()

def check_accessibility():
    # Load keys from environment variables
    access_key = os.getenv("accesskey")
    secret_key = os.getenv("secretaccesskey")

    # Check if they exist
    if access_key and secret_key:
        print("✅ Keys are accessible.")
        print(f"Access Key: {access_key[:4]}****")  # Masked for safety
        print(f"Secret Key: {secret_key[:4]}****")  # Masked for safety
    else:
        print("❌ Keys are missing or not set in .env")

if __name__ == "__main__":
    check_accessibility()