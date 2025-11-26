import re
import os, json
import time
from datetime import datetime
from openai import OpenAI
from dotenv import load_dotenv
from jamaibase import JamAI, types as t

load_dotenv()

API_KEY = os.getenv("OPENAI_API_KEY")
if not API_KEY:
    raise ValueError("OPENAI_API_KEY not found in .env file")
client = OpenAI(api_key=API_KEY)
MODEL_NAME = "o4-mini"

JAMAI_PROJECT_ID = os.getenv("JAMAI_PROJECT_ID")
JAMAI_PAT = os.getenv("JAMAI_PAT")
TABLE_ID = "scrape_result"
if not JAMAI_PROJECT_ID or not JAMAI_PAT:
    raise ValueError("JamAI sucks")
jamai = JamAI(
    project_id=JAMAI_PROJECT_ID,
    token=JAMAI_PAT
)

def verify_claim(text, url):
    prompt = f"""
You are a grant fact-checker. Verify the following grant detail using ONLY the content from the URL.

URL: {url}

Claim to verify:
{text}

Return ONLY a JSON object. No markdown. No backticks. The JSON must contain the following:
- "is_accurate": true/false/unknown
- "explanation": explanation of match / mismatch
- "evidence": quotes or sections from the page
"""
    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content":  "You are a grant fact-checking AI. You MUST respond with ONLY valid JSON. Do NOT include markdown. Do NOT include explanations outside JSON. Do NOT wrap the JSON in backticks. Do NOT add extra text. Output ONLY a valid JSON object."},
            {"role": "user", "content": prompt}
        ]
    )

    return json.loads(response.choices[0].message.content.strip())


def process_input(data):
    results = {}

    if "grantName" in data:
        claim = data["grantName"]["value"]
        source = data["grantName"]["sourceUrl"]
        results["grantName"] = verify_claim(claim, source)

    if "period" in data:
        claim = data["period"]["range"]
        source = data["period"]["sourceUrl"]
        results["period"] = verify_claim(claim, source)

    if "grantDescription" in data:
        claim = data["grantDescription"]["text"]
        source = data["grantDescription"]["sourceUrl"]
        results["grantDescription"] = verify_claim(claim, source)

    if "applicationProcess" in data:
        app = data["applicationProcess"]
        results["applicationProcess"] = {}

        if "steps" in app:
            claim = app["steps"]["description"]
            source = app["steps"]["sourceUrl"]
            results["applicationProcess"]["steps"] = verify_claim(claim, source)

        if "requiredDocuments" in app:
            req = app["requiredDocuments"]
            results["applicationProcess"]["requiredDocuments"] = []

            for file_info in req.get("files", []):
                claim = f"Document required: {file_info['name']}"
                source = file_info["sourceUrl"]

                results["applicationProcess"]["requiredDocuments"].append(
                    verify_claim(claim, source)
                )

    return results

def _parse_model_output_to_json_or_string(raw_text):
    """
    Try to parse raw_text into a Python dict (json). If the model
    returned the literal "failed to verify" (case-insensitive),
    return that exact string. If parsing fails, attempt to extract
    the first {...} JSON-looking substring and parse that. If still
    failing, return the original stripped text so you can inspect it.
    """
    if raw_text is None:
        return "failed to verify"

    text = raw_text.strip()

    if text.lower() == "failed to verify":
        return "failed to verify"

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    brace_match = re.search(r"(\{(?:[^{}]|(?1))*\})", text)
    if brace_match:
        candidate = brace_match.group(1)
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            candidate_clean = candidate.replace("“", '"').replace("”", '"').replace("’", "'")
            candidate_clean = re.sub(r",\s*(\}|])", r"\1", candidate_clean)
            try:
                return json.loads(candidate_clean)
            except json.JSONDecodeError:
                pass

    lowered = text.lower()
    if "failed" in lowered or "unknown" in lowered or "not confident" in lowered:
        return "failed to verify"

    return text

def grant_final(data_id, ori, result):
    prompt = f"""
You are a professional grant fact-checking AI. You receive:

1. The original extracted grant detail JSON: {ori}
2. The initial verification result JSON: {result}

Your job:
STEP 1 — If verify_json.is_accurate == true:
    → Return ONLY the original_json exactly as a JSON object.
    → No markdown. No backticks. No extra fields.

STEP 2 — If verify_json.is_accurate == false OR unknown:
    → Perform external verification using web search.
    → You may search the web, check multiple reliable sources, or re-check the original source.
    → Rebuild a corrected grant JSON following the exact original structure:
        {{
        "grantName": {{
            "value": "...",
            "sourceUrl": "..."
        }},
        "period": {{
            "range": "...",
            "sourceUrl": "..."
        }},
        "grantDescription": {{
            "text": "...",
            "sourceUrl": "..."
        }},
        "applicationProcess": {{
            "steps": {{
                "description": "...",
                "sourceUrl": "..."
            }},
            "requiredDocuments": {{
                "sourceUrl": "...",
                "files": [
                    {{
                        "name": "...",
                        "downloadUrl": "...",
                        "sourceUrl": "..."
                    }}
                ]
            }}
        }}
        }}


STEP 3 — Confidence Check:
    After searching and rebuilding:
    - If you are NOT fully confident in the corrected information:
         → Return EXACTLY this string:
           failed to verify
    - Otherwise, return the corrected JSON (no markdown, no comments).

STRICT RULES:
- Output MUST be either:
    1. A valid JSON object matching the original structure, OR
    2. The exact string: failed to verify
- NEVER return markdown.
- NEVER wrap output in backticks.
- NEVER return explanations outside the JSON.
- NEVER return both text AND JSON. Only one of the two is allowed.
"""
    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content":  "You are a grant fact-checking AI. You MUST follow the exact steps to verify accuracy of the grant details. Output EITHER a valid JSON object or string."},
            {"role": "user", "content": prompt}
        ]
    )

    raw_output = response.choices[0].message.content.strip()
    final = _parse_model_output_to_json_or_string(raw_output)

    if isinstance(final, dict):
        upload_value = json.dumps(final, separators=(",", ":"), ensure_ascii=False)
    else:
        upload_value = str(final)
    
    try:
        print(f"Uploading 1 final json to row: {data_id}...")
        
        response = jamai.table.update_table_rows(
            "action",
            t.MultiRowUpdateRequest(
                table_id=TABLE_ID, 
                data={
                    data_id: {
                        "grant_final": str(upload_value)
                    }
                }
            )
        )

        if response:
            print(f"Successfully updated. hhee")
            print("Server Response:", response)
        else:
            print("Failed to update rows.")
        
    except Exception as e:
        print(f"An error occurred while uploading final table data: {e}")

def fetch_pav_output(row_id):
    try:
        print(f"Fetching 1 json from table: {TABLE_ID}, {row_id}")
        
        response = jamai.table.get_table_row(
            table_type="action",
            table_id=TABLE_ID,
            row_id=row_id
        )

        if response.items:
            print(f"Row retrieved successfully. {response["grant_scrape"]["value"]}")
            return response["grant_scrape"]["value"], response["ID"]
        else:
            print("The table is empty.")
            return None
    except Exception as e:
        print(f"An error occurred while fetching table data: {e}")
        return None
    
def upload_my_output(data_id, my_data):
    try:
        print(f"Uploading 1 json to row: {data_id}...")
        
        response = jamai.table.update_table_rows(
            "action",
            t.MultiRowUpdateRequest(
                table_id=TABLE_ID, 
                data={
                    data_id: {
                        "grant_verified": str(my_data)
                    }
                }
            )
        )

        if response:
            print(f"Successfully updated. hhee")
            print("Server Response:", response)
        else:
            print("Failed to update rows.")
        
    except Exception as e:
        print(f"An error occurred while uploading table data: {e}")

def fetch_every_row():
    try:
        print(f"Fetching every row from table: {TABLE_ID}...")
        
        response = jamai.table.list_table_rows(
            table_type="action",
            table_id=TABLE_ID,
        )

        for row in response.items:
            print(row["ID"])

        if response.items:
            print(f"All retrieved successfully.")
            return [row["ID"] for row in response.items]
        else:
            print("The table is empty.")
            return None
    except Exception as e:
        print(f"An error occurred while fetching table data: {e}")
        return None    

def parse_json(row_data):
    parsed_json = json.loads(row_data)
    return parsed_json

def main_things_to_run():
    id_list = fetch_every_row()
    for each_id in id_list:
        sample_input, data_id = fetch_pav_output(each_id)
        cleaned_input = parse_json(sample_input)
        result = process_input(cleaned_input)
        print(result)
        upload_my_output(data_id, result)
        grant_final(data_id, cleaned_input, result)

if __name__ == "__main__":
    while True:
        now = datetime.now()

        if now.hour == 4 and now.minute == 0:
            print("It's time")
            main_things_to_run()

            time.sleep(61)
            print("Wait for tmr")
        
        else:
            time.sleep(15)