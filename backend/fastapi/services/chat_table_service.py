import httpx
from typing import Dict, Any, Optional
from ..core.config import settings

class ChatTableService:
    def __init__(self):
        self.base_url = settings.jamai_base_url.rstrip("/")
        self.project_id = settings.jamai_project_id
        self.api_key = settings.jamai_api_key
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        self.agent_id = "User_Chat_Agent"

    def ensure_agent(self):
        """
        Ensures the fixed User_Chat_Agent table exists.
        """
        url = f"{self.base_url}/gen_tables/chat"
        payload = {
            "id": self.agent_id,
            "cols": [
                {"id": "User", "dtype": "str"},
                {
                    "id": "AI", 
                    "dtype": "str",
                    "gen_config": {
                        "model": "ellm/qwen/qwen3-30b-a3b-2507",
                        "system_prompt": (
                            "You are a Routing Logic Engine for the MYGeranHub application.\n\n"
                            "**YOUR SOLE FUNCTION:**\n"
                            "Classify the user input and route it accordingly.\n\n"
                            "---\n\n"
                            "### RULE 1: THE TRAP (Priority High)\n"
                            "IF the user input contains **ANY** of the following:\n"
                            "1.  Facts about a company (e.g., location, revenue, industry, size, business type).\n"
                            "2.  A desire for money/funds/grants (e.g., \"I want funding\", \"cari dana\", \"apply grant\").\n"
                            "3.  Phrases like \"Check my eligibility\", \"Cari geran\", \"My business is...\".\n\n"
                            "**ACTION:**\n"
                            "Stop. Do not generate a sentence. Do not say \"Sure\" or \"Let me check\". \n"
                            "Output strictly this token and nothing else:\n"
                            "<<REDIRECT_TO_SEARCH>>\n\n"
                            "---\n\n"
                            "### RULE 2: GENERAL CHAT (Priority Low)\n"
                            "IF and ONLY IF the input does **not** trigger Rule 1 (e.g., greetings, general questions about definitions like \"What is MDEC?\", \"How does this app work?\"):\n"
                            "1.  Reply helpfully as a Malaysian Government Grant consultant.\n"
                            "2.  Use the user's language (BM/English/Manglish).\n\n"
                            "---\n\n"
                            "### IMPORTANT NEGATIVE CONSTRAINTS (For Rule 1):\n"
                            "- DO NOT say \"I will help you find a grant.\"\n"
                            "- DO NOT say \"Redirecting you now...\"\n"
                            "- DO NOT say \"Here is the token.\"\n"
                            "- JUST output the token: <<REDIRECT_TO_SEARCH>>"
                        )
                    }
                }
            ],
        }
        
        try:
            with httpx.Client() as client:
                response = client.post(url, headers=self.headers, json=payload, timeout=30.0)
                if response.status_code not in [200, 409]:
                     print(f"Failed to ensure agent {self.agent_id}: {response.text}")
        except Exception as e:
            print(f"Error ensuring agent: {e}")

    def create_chat_table(self, session_id: str) -> Dict[str, Any]:
        """
        Creates a new Chat Table in JamAI Base for the given session, by duplicating the User_Chat_Agent.
        """
        self.ensure_agent()

        # Table ID must be unique.
        table_id = f"{self.agent_id}_{session_id}"
        
        # Use the duplicate endpoint to create a child table
        url = f"{self.base_url}/gen_tables/chat/duplicate"
        
        params = {
            "table_id_src": self.agent_id,
            "table_id_dst": table_id,
            "include_data": False,
            "create_as_child": True
        }

        try:
            with httpx.Client() as client:
                response = client.post(url, headers=self.headers, params=params, timeout=30.0)
                if response.status_code == 200:
                    return response.json()
                elif response.status_code == 409:
                    # Table might already exist
                    # We should probably fetch it to return the details
                    return {"id": table_id, "status": "exists", "parent_id": self.agent_id}
                else:
                    print(f"Failed to create table. Status: {response.status_code}, Response: {response.text}")
                    raise Exception(f"JamAI API Error: {response.text}")
        except Exception as e:
            print(f"Error creating chat table: {e}")
            raise

    def send_message(self, session_id: str, message: str) -> str:
        """
        Sends a message to the chat table and returns the AI response.
        """
        table_id = f"{self.agent_id}_{session_id}"
        url = f"{self.base_url}/gen_tables/chat/rows/add"
        
        payload = {
            "table_id": table_id,
            "data": [{"User": message}],
            "stream": False
        }

        try:
            with httpx.Client() as client:
                response = client.post(url, headers=self.headers, json=payload, timeout=60.0)
                if response.status_code == 200:
                    data = response.json()
                    # Extract AI response from the first row
                    rows = data.get("rows", [])
                    if rows:
                        ai_col = rows[0].get("columns", {}).get("AI")
                        if ai_col:
                            choices = ai_col.get("choices", [])
                            if choices:
                                return choices[0].get("message", {}).get("content", "")
                    return "Error: No response from AI."
                else:
                    print(f"Failed to send message. Status: {response.status_code}, Response: {response.text}")
                    raise Exception(f"JamAI API Error: {response.text}")
        except Exception as e:
            print(f"Error sending message: {e}")
            raise

chat_table_service = ChatTableService()
