import httpx
from typing import List, Dict, Any, Sequence

class JamAIClient:
    def __init__(self, base_url: str, project_id: str, api_key: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.project_id = project_id
        self.api_key = api_key
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def generate_reply(self, messages: List[Dict[str, str]], model: str = "openai/gpt-4o-mini") -> str:
        """
        Generates a reply using the JamAI Base API (OpenAI-compatible chat completions).
        """
        url = f"{self.base_url}/projects/{self.project_id}/chat/completions"
        
        payload = {
            "model": model,
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 1000,
        }

        try:
            with httpx.Client() as client:
                response = client.post(url, headers=self.headers, json=payload, timeout=30.0)
                response.raise_for_status()
                data = response.json()
                # Assuming OpenAI-compatible response structure
                return data["choices"][0]["message"]["content"]
        except Exception as e:
            print(f"Error calling JamAI API: {e}")
            return f"Error: {str(e)}"



