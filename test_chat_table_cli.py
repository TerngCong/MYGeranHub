import sys
import os
import uuid
import argparse

# Add the current directory to sys.path to allow imports from backend
sys.path.append(os.getcwd())

try:
    from server.services.chat_table_service import chat_table_service
except ImportError as e:
    print(f"Error importing service: {e}")
    print("Make sure you are running this script from the root directory of the project (MYGeranHub).")
    sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="Test Chat Table Creation via CLI")
    parser.add_argument("--session-id", type=str, help="Session ID to use. If not provided, a random UUID will be generated.")
    args = parser.parse_args()

    session_id = args.session_id
    if not session_id:
        session_id = str(uuid.uuid4())[:8]
        print(f"No session ID provided. Generated random session ID: {session_id}")

    print(f"Attempting to create chat table for session: {session_id}...")
    
    try:
        # Create/Ensure table exists
        result = chat_table_service.create_chat_table(session_id)
        print(f"Chat Table Ready: {result.get('id')}")
        print("---------------------------------------")
        print("Type 'exit' or 'quit' to stop.")
        
        while True:
            user_input = input("\nUser: ")
            if user_input.lower() in ["exit", "quit"]:
                break
            
            if not user_input.strip():
                continue

            print("AI is thinking...", end="\r")
            try:
                response = chat_table_service.send_message(session_id, user_input)
                print(f"AI: {response}")
            except Exception as e:
                print(f"\nError sending message: {e}")

    except Exception as e:
        print(f"\nError initializing chat session: {e}")

if __name__ == "__main__":
    main()
