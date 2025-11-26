import httpx
from typing import Any, Dict, Tuple

from ..core.config import settings


class ChatTableService:
    def __init__(self):
        self.base_url = settings.jamai_base_url.rstrip("/") if settings.jamai_base_url else None
        self.project_id = settings.jamai_project_id
        self.api_key = settings.jamai_api_key
        self._headers: Dict[str, str] | None = None
        self.agent_id = "User_Chat_Agent"

    def _ensure_configured(self) -> Tuple[str, Dict[str, str]]:
        missing = []
        if not self.base_url:
            missing.append("JAMAI_BASE_URL")
        if not self.project_id:
            missing.append("JAMAI_PROJECT_ID")
        if not self.api_key:
            missing.append("JAMAI_API_KEY")

        if missing:
            missing_vars = ", ".join(missing)
            raise RuntimeError(
                f"JamAI integration is not configured. Set the following environment variables: {missing_vars}"
            )

        if self._headers is None:
            self._headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }

        return self.base_url, self._headers

    def ensure_agent(self):
        """
        Ensures the fixed User_Chat_Agent table exists.
        """
        base_url, headers = self._ensure_configured()
        url = f"{base_url}/gen_tables/chat"
        payload = {
            "id": self.agent_id,
            "cols": [
                {"id": "User", "dtype": "str"},
                {
                    "id": "AI", 
                    "dtype": "str",
                    "gen_config": {
                        "model": "gemini-1.5-flash",
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
                response = client.post(url, headers=headers, json=payload, timeout=30.0)
                if response.status_code not in [200, 409]:
                     print(f"Failed to ensure agent {self.agent_id}: {response.text}")
        except Exception as e:
            print(f"Error ensuring agent: {e}")

    def create_chat_table(self, user_id: str) -> Dict[str, Any]:
        """
        Creates a new Chat Table in JamAI Base for the given user, by duplicating the User_Chat_Agent.
        """
        self.ensure_agent()

        # Table ID must be unique.
        table_id = f"{self.agent_id}_{user_id}"
        
        # Use the duplicate endpoint to create a child table
        base_url, headers = self._ensure_configured()
        url = f"{base_url}/gen_tables/chat/duplicate"
        
        params = {
            "table_id_src": self.agent_id,
            "table_id_dst": table_id,
            "include_data": False,
            "create_as_child": True
        }

        try:
            with httpx.Client() as client:
                response = client.post(url, headers=headers, params=params, timeout=30.0)
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

    def send_message(self, user_id: str, message: str) -> str:
        """
        Sends a message to the chat table and returns the AI response.
        """
        table_id = f"{self.agent_id}_{user_id}"
        base_url, headers = self._ensure_configured()
        url = f"{base_url}/gen_tables/chat/rows/add"
        
        payload = {
            "table_id": table_id,
            "data": [{"User": message}],
            "stream": False
        }

        try:
            with httpx.Client() as client:
                response = client.post(url, headers=headers, json=payload, timeout=60.0)
                
                # If table not found (404), try to create it and retry
                if response.status_code == 404:
                    print(f"Table {table_id} not found. Creating it...")
                    self.create_chat_table(user_id)
                    # Retry the request
                    response = client.post(url, headers=headers, json=payload, timeout=60.0)

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

    def run_scout_action(self, user_text: str) -> str:
        """
        Runs the Scout Action Table to determine follow-up questions or completion.
        """
        base_url, headers = self._ensure_configured()
        url = f"{base_url}/gen_tables/action/rows/add"
        
        # Explicitly targeting the Action Table ID
        # User confirmed the table name is "First_Grant"
        table_id = "First_Grant"
        
        # User confirmed the column name is "Basic_Company_Profile"
        payload = {
            "table_id": table_id,
            "data": [{"Basic_Company_Profile": user_text}],
            "stream": False
        }
        
        print(f"DEBUG: Sending to Action Table '{table_id}' with payload: {payload}")

        try:
            with httpx.Client() as client:
                response = client.post(url, headers=headers, json=payload, timeout=60.0)
                print(f"DEBUG: Action Table Response ({response.status_code}): {response.text}")
                
                if response.status_code == 200:
                    data = response.json()
                    rows = data.get("rows", [])
                    if rows:
                        # Extract Follow_Up_Questions from the response
                        cols = rows[0].get("columns", {})
                        follow_up = cols.get("Follow_Up_Questions")
                        if follow_up:
                            # Handle both direct value or choices structure depending on API response
                            if isinstance(follow_up, dict) and "choices" in follow_up:
                                choices = follow_up.get("choices", [])
                                if choices:
                                    return choices[0].get("message", {}).get("content", "")
                            elif isinstance(follow_up, dict) and "value" in follow_up:
                                return str(follow_up.get("value", ""))
                            elif isinstance(follow_up, str):
                                return follow_up
                            
                    return "Error: No output from Scout Action."
                else:
                    print(f"Failed to run scout action. Status: {response.status_code}, Response: {response.text}")
                    raise Exception(f"JamAI API Error: {response.text}")
        except Exception as e:
            print(f"Error running scout action: {e}")
            raise

    def handle_incoming_message(self, user_id: str, user_text: str) -> Dict[str, Any]:
        """
        Orchestrates the chat flow:
        1. Sends message to Chat Table.
        2. Checks for redirect token.
        3. If redirect, calls Scout Action Table.
        4. Returns appropriate response format.
        """
        # Step A: Call existing send_message (Chat Table)
        chat_response = self.send_message(user_id, user_text)

        # Step B: Check for redirect token
        if "<<REDIRECT_TO_SEARCH>>" in chat_response:
            # Do NOT return this text to user. Call Scout Action.
            scout_output = self.run_scout_action(user_text)
            
            # Logic Gate
            if "COMPLETE" in scout_output:
                return {
                    "status": "trigger_judge", 
                    "payload": user_text
                }
            else:
                # It's a question from the Scout
                return {
                    "status": "reply", 
                    "message": [scout_output]
                }
        else:
            # Normal Chat
            return {
                "status": "reply", 
                "message": [chat_response]
            }

chat_table_service = ChatTableService()
