# agents/web_scraper_agent.py
import google.generativeai as genai
from jamaibase import JamAI, types as t
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
import json
import re
import os
from datetime import datetime
import logging
import time
from dataclasses import dataclass
import uuid
import schedule
import pytz

# Load environment variables
load_dotenv()
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
JAMAIBASE_PROJECT_ID = os.getenv('JAMAIBASE_PROJECT_ID')

# Initialize JamAI client globally
jamai = JamAI(project_id=JAMAIBASE_PROJECT_ID, token=os.getenv('JAMAIBASE_API_KEY'))

@dataclass
class GrantEntry:
    """Structure for grant entries in JamAIBase scrap_result Table"""
    id: str
    grant_scrap: str  # Store as JSON string for the table
    updated_at: str
    status: str = "active"

class WebScraperAgent:
    """Agent 1: Performs reliable sequential web scraping"""
    
    def __init__(self, gemini_api_key: str, jamai_client):
        self.gemini_api_key = gemini_api_key
        self.jamai_client = jamai_client
        self.model = None
        self.model_name = "gemini-2.0-flash"
        self.grant_entries: List[GrantEntry] = []
        self.configure_gemini()
    
    def configure_gemini(self):
        """Configure Gemini AI for comprehensive web search"""
        try:
            genai.configure(api_key=self.gemini_api_key)
            self.model = genai.GenerativeModel(self.model_name)
            logging.info(f"✅ WebScraperAgent initialized with {self.model_name}")
        except Exception as e:
            logging.error(f"❌ Gemini configuration failed: {e}")
            self.model = None

    def scrape_all_grants(self) -> List[GrantEntry]:
        """
        Main method: Simple sequential scraping with limit to save quota
        """
        if not self.model:
            logging.error("❌ AI model not available for web search")
            return []
        
        try:
            logging.info("🔍 Starting web search for Malaysian grants...")
            
            # Step 1: Get comprehensive list of grant names (limited to save quota)
            grant_names = self._get_comprehensive_grant_list()
            
            if not grant_names:
                logging.error("❌ No grant names found to scrape")
                return []
            
            logging.info(f"📋 Found {len(grant_names)} grants for processing")
            
            # Step 2: Get existing grants to avoid duplicates
            existing_grants = self.jamai_client.get_grants_from_table()
            existing_grant_names = self._get_existing_grant_names(existing_grants)
            logging.info(f"📊 Found {len(existing_grant_names)} existing grants in table")
            
            # Step 3: Filter out existing grants
            new_grant_names = [name for name in grant_names if name not in existing_grant_names]
            
            if not new_grant_names:
                logging.info("✅ All grants already exist in table, no new grants to scrape")
                return []
            
            logging.info(f"🆕 Found {len(new_grant_names)} new grants to scrape")
            
            # Step 4: Sequential scraping only for new grants
            scraped_grants = self._sequential_scraping(new_grant_names)
            
            # Step 5: Convert to grant entries
            grant_entries = self._create_grant_entries(scraped_grants)
            
            logging.info(f"✅ Web search completed. Found {len(grant_entries)} new grants")
            return grant_entries
            
        except Exception as e:
            logging.error(f"❌ Web search failed: {e}")
            return []

    def _get_existing_grant_names(self, existing_grants: List[Dict]) -> List[str]:
        """Extract grant names from existing grants to avoid duplicates"""
        existing_names = []
        for grant in existing_grants:
            grant_data = grant.get("grant_scrap", {})
            grant_name = grant_data.get("grantName", {}).get("value", "").strip()
            if grant_name:
                existing_names.append(grant_name)
        return existing_names

    def _get_comprehensive_grant_list(self) -> List[str]:
        """Get a comprehensive list of Malaysian grant names with limit"""
        try:
            prompt = """
            You are an expert research assistant specialized in Malaysian government grants.
            
            TASK: Provide a COMPREHENSIVE list of CURRENT and RELEVANT Malaysian government grant names.
            Focus on grants that are currently active or recently closed.

            SEARCH CRITERIA:
            - Include CURRENT Malaysian government grants
            - Include ACTIVE and RECENTLY CLOSED grants (within last 6 months)
            - Include grants from major Malaysian government agencies
            - Include federal and state government grants
            - Include grants from government-linked companies (GLCs)

            RETURN ONLY A JSON ARRAY OF GRANT NAMES (MAXIMUM 15 GRANTS):
            [
              "Exact Official Grant Name 1",
              "Exact Official Grant Name 2", 
              "Exact Official Grant Name 3",
              ...
            ]

            IMPORTANT: 
            - Return MAXIMUM 15 most relevant and current grants
            - Use exact official grant names
            - DEDUPLICATE the list to avoid repeats
            - Return ONLY valid JSON array, no additional text
            """
            
            generation_config = {
                "temperature": 0.7,
                "top_p": 0.9,
                "top_k": 50,
                "max_output_tokens": 1024,  # Reduced to save tokens
            }
            
            response = self._make_ai_request_with_retry(prompt, generation_config)
            if not response:
                return []
            
            grant_names = self._parse_grant_names_response(response.text)
            # Limit to 10 grants to save quota while maintaining functionality
            return grant_names[:10]
            
        except Exception as e:
            logging.error(f"❌ Failed to get grant list: {e}")
            return []

    def _sequential_scraping(self, grant_names: List[str]) -> List[Dict]:
        """Perform reliable sequential scraping"""
        scraped_grants = []
        total_grants = len(grant_names)
        
        logging.info(f"🔄 Starting sequential scraping for {total_grants} grants...")
        
        for i, grant_name in enumerate(grant_names, 1):
            try:
                logging.info(f"📝 Processing grant {i}/{total_grants}: {grant_name}")
                
                # Scrape individual grant
                grant_data = self._search_single_grant_ai(grant_name)
                
                if grant_data and self._validate_exact_structure(grant_data):
                    scraped_grants.append(grant_data)
                    logging.info(f"✅ Successfully scraped: {grant_name}")
                else:
                    logging.warning(f"⚠️ Failed to scrape valid data for: {grant_name}")
                
                # Add delay to avoid rate limiting
                time.sleep(2)  # Reduced delay to 2 seconds
                
            except Exception as e:
                logging.error(f"❌ Error scraping {grant_name}: {e}")
                continue
        
        logging.info(f"📊 Sequential scraping completed: {len(scraped_grants)}/{total_grants} grants scraped")
        return scraped_grants

    def _search_single_grant_ai(self, grant_name: str) -> Optional[Dict[str, Any]]:
        """Perform detailed AI-powered search for a single grant"""
        try:
            prompt = f"""
            You are an expert research assistant specialized in Malaysian government grants.
            
            TASK: Perform a DETAILED web search for the specific Malaysian grant: "{grant_name}"
            Provide COMPLETE and ACCURATE information about this grant.

            SEARCH FOR COMPREHENSIVE INFORMATION ABOUT: {grant_name}

            REQUIREMENTS:
            - Provide REALISTIC and VERIFIABLE information
            - Include ACTUAL official URLs where possible
            - Be THOROUGH in your research for this specific grant
            - Ensure all information is accurate and detailed

            RETURN DATA IN THIS EXACT JSON FORMAT - NO CHANGES TO STRUCTURE:
            {{
              "grantName": {{
                "value": "Exact official grant name",
                "sourceUrl": "Official program website URL"
              }},
              "period": {{
                "range": "Specific date range or 'Ongoing'",
                "sourceUrl": "URL where application period is specified"
              }},
              "grantDescription": {{
                "text": "Comprehensive description covering: purpose, eligibility criteria, funding amount, target beneficiaries, key benefits, and expected outcomes.",
                "sourceUrl": "URL where detailed description is available"
              }},
              "applicationProcess": {{
                "steps": {{
                  "description": "Detailed step-by-step application instructions",
                  "sourceUrl": "URL where application process is detailed"
                }},
                "requiredDocuments": {{
                  "sourceUrl": "URL where document requirements are listed",
                  "files": [
                    {{
                      "name": "Specific document name as required by grant",
                      "downloadUrl": "Actual URL to download template or official source", 
                      "sourceUrl": "URL where this document requirement is mentioned"
                    }}
                  ]
                }}
              }}
            }}

            IMPORTANT: 
            - RETURN THE EXACT STRUCTURE AS SPECIFIED - NO MODIFICATIONS
            - If downloadUrl is not available, use null but provide sourceUrl
            - Ensure all URLs are realistic and verifiable
            """
            
            generation_config = {
                "temperature": 0.3,
                "top_p": 0.9,
                "top_k": 40,
                "max_output_tokens": 2048,  # Reduced to save tokens
            }
            
            response = self._make_ai_request_with_retry(prompt, generation_config)
            if not response:
                return None
            
            grant_data = self._parse_single_grant_response(response.text)
            return grant_data
            
        except Exception as e:
            logging.error(f"❌ Single grant search failed for {grant_name}: {e}")
            return None

    def _make_ai_request_with_retry(self, prompt: str, generation_config: Dict, max_retries: int = 3) -> Optional[Any]:
        """Make AI request with retry logic for quota issues"""
        for attempt in range(max_retries):
            try:
                response = self.model.generate_content(
                    prompt,
                    generation_config=generation_config
                )
                return response
            except Exception as e:
                if "quota" in str(e).lower() or "429" in str(e):
                    wait_time = (attempt + 1) * 30
                    logging.warning(f"⚠️ Quota limit hit, waiting {wait_time} seconds...")
                    time.sleep(wait_time)
                    continue
                else:
                    logging.error(f"❌ AI request error: {e}")
                    return None
        logging.error("❌ All retries failed due to quota limits")
        return None

    def _parse_grant_names_response(self, response_text: str) -> List[str]:
        """Parse AI response and extract grant names list"""
        try:
            cleaned_text = re.sub(r'```json\s*|\s*```', '', response_text).strip()
            json_match = re.search(r'(\[.*\])', cleaned_text, re.DOTALL)
            if json_match:
                cleaned_text = json_match.group(1)
            
            grant_names = json.loads(cleaned_text)
            
            if isinstance(grant_names, list) and all(isinstance(name, str) for name in grant_names):
                logging.info(f"✅ Retrieved {len(grant_names)} grant names for processing")
                return grant_names
            else:
                logging.error("❌ Invalid grant names format")
                return []
            
        except json.JSONDecodeError as e:
            logging.error(f"❌ Failed to parse grant names as JSON: {e}")
            logging.error(f"❌ Response text was: {response_text[:500]}...")
            return []
        except Exception as e:
            logging.error(f"❌ Unexpected error parsing grant names: {e}")
            return []

    def _parse_single_grant_response(self, response_text: str) -> Optional[Dict[str, Any]]:
        """Parse AI response for a single grant"""
        try:
            cleaned_text = re.sub(r'```json\s*|\s*```', '', response_text).strip()
            json_match = re.search(r'(\{.*\})', cleaned_text, re.DOTALL)
            if json_match:
                cleaned_text = json_match.group(1)
            
            grant_data = json.loads(cleaned_text)
            
            if self._validate_exact_structure(grant_data):
                return grant_data
            else:
                logging.error("❌ Single grant response has invalid structure")
                return None
            
        except json.JSONDecodeError as e:
            logging.error(f"❌ Failed to parse single grant response as JSON: {e}")
            return None
        except Exception as e:
            logging.error(f"❌ Unexpected error parsing single grant: {e}")
            return None

    def _validate_exact_structure(self, grant: Dict) -> bool:
        """Validate that grant matches EXACT required structure"""
        try:
            required_structure = {
                "grantName": ["value", "sourceUrl"],
                "period": ["range", "sourceUrl"],
                "grantDescription": ["text", "sourceUrl"],
                "applicationProcess": {
                    "steps": ["description", "sourceUrl"],
                    "requiredDocuments": ["sourceUrl", "files"]
                }
            }
            
            # Check top-level keys
            if not all(key in grant for key in required_structure.keys()):
                return False
            
            # Check grantName structure
            if not all(key in grant["grantName"] for key in required_structure["grantName"]):
                return False
            
            # Check period structure
            if not all(key in grant["period"] for key in required_structure["period"]):
                return False
            
            # Check grantDescription structure
            if not all(key in grant["grantDescription"] for key in required_structure["grantDescription"]):
                return False
            
            # Check applicationProcess structure
            app_process = grant["applicationProcess"]
            if not all(key in app_process for key in required_structure["applicationProcess"].keys()):
                return False
            
            # Check steps structure
            if not all(key in app_process["steps"] for key in required_structure["applicationProcess"]["steps"]):
                return False
            
            # Check requiredDocuments structure
            req_docs = app_process["requiredDocuments"]
            if not all(key in req_docs for key in required_structure["applicationProcess"]["requiredDocuments"]):
                return False
            
            # Check files array structure
            if "files" in req_docs and isinstance(req_docs["files"], list):
                for file_item in req_docs["files"]:
                    if not all(key in file_item for key in ["name", "downloadUrl", "sourceUrl"]):
                        return False
            
            return True
            
        except Exception:
            return False

    def _create_grant_entries(self, grants_data: List[Dict[str, Any]]) -> List[GrantEntry]:
        """Convert grants data to grant entries - KEEPING EXACT FORMAT"""
        grant_entries = []
        
        for grant_data in grants_data:
            entry_id = str(uuid.uuid4())
            
            # Convert grant_data to JSON string for the grant_scrap column
            grant_scrap_json = json.dumps(grant_data, ensure_ascii=False)
            
            grant_entry = GrantEntry(
                id=entry_id,
                grant_scrap=grant_scrap_json,  # Now storing as JSON string
                updated_at=datetime.now(pytz.timezone('Asia/Kuala_Lumpur')).isoformat(),
                status="active"
            )
            
            grant_entries.append(grant_entry)
            logging.info(f"📝 Created grant entry: {entry_id} - {grant_data['grantName']['value']}")
        
        return grant_entries


class JamAIBaseClient:
    """Client for interacting with JamAIBase API using proper SDK methods"""
    
    def __init__(self):
        # Use the globally initialized jamai client
        self.client = jamai
    
    def add_grant_entries_to_scrap_result_table(self, grant_entries: List[GrantEntry]) -> bool:
        """
        Add grant entries to JamAIBase scrap_result table using proper SDK methods
        """
        if not self.client:
            logging.error("❌ JamAI client not initialized")
            return False
            
        try:
            # Prepare data for JamAIBase table
            rows_data = []
            for entry in grant_entries:
                row_data = {
                    "id": entry.id,
                    "updated_at": entry.updated_at,
                    "grant_scrap": entry.grant_scrap,  # Already a JSON string
                    "status": entry.status
                }
                rows_data.append(row_data)
            
            # Use JamAIBase SDK method for adding rows (non-streaming)
            completion = self.client.table.add_table_rows(
                "action",
                t.MultiRowAddRequest(
                    table_id="scrap_result",  # Using scrap_result as table_id
                    data=rows_data,
                    stream=False  # Non-streaming for bulk operations
                ),
            )
            
            logging.info(f"✅ Successfully added {len(grant_entries)} grants to JamAIBase scrap_result table")
            logging.info(f"📊 Added rows: {len(completion.rows)}")
            
            # Verify the data was actually added by checking the content
            for row in completion.rows:
                if hasattr(row, 'columns') and 'grant_scrap' in row.columns:
                    grant_scrap_value = row.columns['grant_scrap']
                    if grant_scrap_value and hasattr(grant_scrap_value, 'text'):
                        logging.info(f"📝 Verified grant data added: {grant_scrap_value.text[:100]}...")
                    elif grant_scrap_value and isinstance(grant_scrap_value, dict):
                        logging.info(f"📝 Verified grant data added (dict): {str(grant_scrap_value)[:100]}...")
            
            return True
                        
        except Exception as e:
            logging.error(f"❌ Error adding grants to JamAIBase: {e}")
            return False

    def get_grants_from_table(self) -> List[Dict]:
        """Get all grants from scrap_result table using proper SDK method"""
        if not self.client:
            logging.error("❌ JamAI client not initialized")
            return []
            
        try:
            # Use JamAIBase SDK method for listing rows - following documentation format
            rows = self.client.table.list_table_rows("action", "scrap_result")
            
            grants = []
            # Paginated items - following documentation format
            for row in rows.items:
                # Handle different data types for grant_scrap
                grant_scrap_data = row.get("grant_scrap", {})
                
                # If grant_scrap is already a dict, use it directly
                if isinstance(grant_scrap_data, dict):
                    grant_data = grant_scrap_data
                # If grant_scrap is a string, try to parse it as JSON
                elif isinstance(grant_scrap_data, str):
                    try:
                        grant_data = json.loads(grant_scrap_data)
                    except json.JSONDecodeError:
                        logging.warning(f"⚠️ Failed to parse grant_scrap JSON for row {row.get('ID')}")
                        grant_data = {}
                else:
                    grant_data = {}
                
                grant_info = {
                    "id": row.get("ID"),
                    "updated_at": row.get("updated_at", ""),
                    "grant_scrap": grant_data,  # Always a dict for processing
                    "status": row.get("status", "active")
                }
                grants.append(grant_info)
                
                grant_name = grant_data.get('grantName', {}).get('value', 'Unknown')
                logging.info(f"📋 Retrieved grant: {grant_info['id']} - {grant_name}")
            
            logging.info(f"📋 Retrieved {len(grants)} grants from scrap_result table")
            return grants
            
        except Exception as e:
            logging.error(f"❌ Error getting grants from table: {e}")
            return []

    def update_grant_in_table(self, grant_id: str, updated_data: Dict, status: str = "validated") -> bool:
        """Update a single grant in the scrap_result table using proper SDK method"""
        if not self.client:
            logging.error("❌ JamAI client not initialized")
            return False
            
        try:
            # Convert updated_data to JSON string for the grant_scrap column
            updated_data_json = json.dumps(updated_data, ensure_ascii=False)
            
            # Prepare update data
            update_data = {
                "id": grant_id,
                "grant_scrap": updated_data_json,  # Store as JSON string
                "updated_at": datetime.now(pytz.timezone('Asia/Kuala_Lumpur')).isoformat(),
                "status": status
            }
            
            # Use JamAIBase SDK method for updating rows
            completion = self.client.table.update_table_rows(
                "action",
                t.MultiRowUpdateRequest(
                    table_id="scrap_result",
                    data=[update_data]
                ),
            )
            
            logging.info(f"✅ Successfully updated grant: {grant_id}")
            
            # Verify the update
            for row in completion.rows:
                if hasattr(row, 'columns') and 'grant_scrap' in row.columns:
                    grant_scrap_value = row.columns['grant_scrap']
                    if grant_scrap_value and hasattr(grant_scrap_value, 'text'):
                        logging.info(f"📝 Verified grant data updated: {grant_scrap_value.text[:100]}...")
                    elif grant_scrap_value and isinstance(grant_scrap_value, dict):
                        logging.info(f"📝 Verified grant data updated (dict): {str(grant_scrap_value)[:100]}...")
            
            return True
                
        except Exception as e:
            logging.error(f"❌ Error updating grant {grant_id}: {e}")
            return False

    def find_grant_by_name(self, grant_name: str) -> Optional[Dict]:
        """Find an existing grant by name to avoid duplicates"""
        try:
            grants = self.get_grants_from_table()
            for grant in grants:
                grant_data = grant.get("grant_scrap", {})
                existing_name = grant_data.get("grantName", {}).get("value", "").strip()
                if existing_name.lower() == grant_name.lower():
                    return grant
            return None
        except Exception as e:
            logging.error(f"❌ Error finding grant by name {grant_name}: {e}")
            return None


class GrantValidatorAgent:
    """Agent 2: Validates and updates grant information in the table"""
    
    def __init__(self, gemini_api_key: str, jamai_client: JamAIBaseClient):
        self.gemini_api_key = gemini_api_key
        self.jamai_client = jamai_client
        self.model = None
        self.model_name = "gemini-2.0-flash"
        self.configure_gemini()
    
    def configure_gemini(self):
        """Configure Gemini AI for validation"""
        try:
            genai.configure(api_key=self.gemini_api_key)
            self.model = genai.GenerativeModel(self.model_name)
            logging.info(f"✅ GrantValidatorAgent initialized with {self.model_name}")
        except Exception as e:
            logging.error(f"❌ Gemini configuration failed for validator: {e}")
            self.model = None

    def validate_and_update_grants(self) -> Dict[str, Any]:
        """
        Validate all grants in scrap_result table and update if needed
        """
        if not self.model:
            logging.error("❌ AI model not available for validation")
            return {"success": False, "error": "AI model not available"}
        
        try:
            # Step 1: Get all grants from scrap_result table using proper method
            grants = self.jamai_client.get_grants_from_table()
            if not grants:
                logging.warning("⚠️ No grants found in table for validation")
                return {"success": True, "grants_checked": 0, "grants_updated": 0}
            
            logging.info(f"🔍 Starting validation for {len(grants)} grants...")
            
            # Step 2: Validate each grant
            updated_count = 0
            for grant in grants:
                try:
                    if self._validate_and_update_single_grant(grant):
                        updated_count += 1
                    time.sleep(1)  # Small delay between validations
                except Exception as e:
                    logging.error(f"❌ Error validating grant {grant.get('id', 'unknown')}: {e}")
                    continue
            
            logging.info(f"✅ Validation completed: {updated_count}/{len(grants)} grants updated")
            return {
                "success": True,
                "grants_checked": len(grants),
                "grants_updated": updated_count
            }
            
        except Exception as e:
            logging.error(f"❌ Grant validation failed: {e}")
            return {"success": False, "error": str(e)}

    def _validate_and_update_single_grant(self, grant: Dict) -> bool:
        """Validate and update a single grant if needed"""
        try:
            grant_data = grant.get("grant_scrap", {})
            grant_name = grant_data.get("grantName", {}).get("value", "Unknown Grant")
            
            # Check if grant_data is empty or missing critical information
            if not grant_data or not grant_data.get("grantName", {}).get("value"):
                logging.warning(f"⚠️ Grant {grant.get('id')} has incomplete data, skipping validation")
                return False
            
            prompt = f"""
            Analyze this grant data for accuracy and completeness:
            
            GRANT DATA:
            {json.dumps(grant_data, indent=2)}
            
            TASK: Check if this grant information is:
            1. ACCURATE - Information matches official sources
            2. COMPLETE - No missing critical information
            3. CURRENT - Information is up-to-date
            
            If you find any:
            - Missing information
            - Inaccurate details  
            - Outdated information
            - Broken URLs
            
            Return the CORRECTED and UPDATED grant data in the EXACT same JSON format.
            
            If the data is already accurate and complete, return the ORIGINAL data unchanged.
            
            RETURN ONLY THE JSON, no additional text.
            """
            
            generation_config = {
                "temperature": 0.1,  # Low temperature for consistency
                "top_p": 0.9,
                "top_k": 40,
                "max_output_tokens": 2048,
            }
            
            response = self._make_ai_request_with_retry(prompt, generation_config)
            if not response:
                return False
            
            # Parse the validated data
            validated_data = self._parse_validated_response(response.text)
            if not validated_data:
                return False
            
            # Check if update is needed
            if json.dumps(validated_data, sort_keys=True) != json.dumps(grant_data, sort_keys=True):
                logging.info(f"🔄 Updating grant {grant_name} with validated data")
                # Update the grant in the table using proper method
                return self.jamai_client.update_grant_in_table(grant["id"], validated_data)
            else:
                logging.info(f"✅ Grant {grant_name} is already accurate, no update needed")
            
            return False
            
        except Exception as e:
            logging.error(f"❌ Error validating grant {grant.get('id', 'unknown')}: {e}")
            return False

    def _make_ai_request_with_retry(self, prompt: str, generation_config: Dict, max_retries: int = 3) -> Optional[Any]:
        """Make AI request with retry logic for quota issues"""
        for attempt in range(max_retries):
            try:
                response = self.model.generate_content(
                    prompt,
                    generation_config=generation_config
                )
                return response
            except Exception as e:
                if "quota" in str(e).lower() or "429" in str(e):
                    wait_time = (attempt + 1) * 30
                    logging.warning(f"⚠️ Quota limit hit, waiting {wait_time} seconds...")
                    time.sleep(wait_time)
                    continue
                else:
                    logging.error(f"❌ AI request error: {e}")
                    return None
        logging.error("❌ All retries failed due to quota limits")
        return None

    def _parse_validated_response(self, response_text: str) -> Optional[Dict]:
        """Parse the validation response"""
        try:
            cleaned_text = re.sub(r'```json\s*|\s*```', '', response_text).strip()
            json_match = re.search(r'(\{.*\})', cleaned_text, re.DOTALL)
            if json_match:
                cleaned_text = json_match.group(1)
            
            return json.loads(cleaned_text)
        except Exception as e:
            logging.error(f"❌ Failed to parse validation response: {e}")
            return None


# Cron Job Execution Function
def cron_web_search() -> Dict[str, Any]:
    """
    Main cron job function to be scheduled
    - Scrapes Malaysian grants using reliable sequential system
    - Adds them to JamAIBase scrap_result table
    - Validates and updates existing grants
    """
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('grant_scraper.log'),
            logging.StreamHandler()
        ]
    )
    
    if not GEMINI_API_KEY:
        logging.error("❌ GEMINI_API_KEY not found")
        return {"success": False, "error": "GEMINI_API_KEY not found"}
    
    if not os.getenv('JAMAIBASE_API_KEY'):
        logging.error("❌ JAMAIBASE_API_KEY not found")
        return {"success": False, "error": "JAMAIBASE_API_KEY not found"}
    
    if not JAMAIBASE_PROJECT_ID:
        logging.error("❌ JAMAIBASE_PROJECT_ID not found")
        return {"success": False, "error": "JAMAIBASE_PROJECT_ID not found"}
    
    try:
        # Initialize JamAIBase client first
        jamai_client = JamAIBaseClient()
        
        # Initialize web scraper agent with jamai_client for duplicate detection
        web_scraper = WebScraperAgent(GEMINI_API_KEY, jamai_client)
        
        # Initialize validator agent
        validator_agent = GrantValidatorAgent(GEMINI_API_KEY, jamai_client)
        
        # Perform web search (now with duplicate detection)
        logging.info("🚀 Starting web scraping for Malaysian grants...")
        grant_entries = web_scraper.scrape_all_grants()
        
        if grant_entries:
            # Add grants to JamAIBase scrap_result table using proper method
            logging.info("💾 Adding grants to JamAIBase scrap_result table...")
            success = jamai_client.add_grant_entries_to_scrap_result_table(grant_entries)
            
            if success:
                logging.info(f"✅ Successfully added {len(grant_entries)} grants to scrap_result table")
                
                # Wait a moment for data to be processed
                time.sleep(2)
                
                # Step 2: Validate and update existing grants
                logging.info("🔍 Starting grant validation process...")
                validation_result = validator_agent.validate_and_update_grants()
            else:
                logging.error("❌ Failed to add grants to scrap_result table")
                validation_result = {"success": False, "grants_checked": 0, "grants_updated": 0}
        else:
            logging.warning("⚠️ No new grants found in web search")
            success = True  # Consider it success if no new grants found
            # Still validate existing grants
            logging.info("🔍 Starting grant validation process for existing grants...")
            validation_result = validator_agent.validate_and_update_grants()
        
        # Prepare summary
        summary = {
            "success": success and validation_result["success"],
            "grants_found": len(grant_entries),
            "grants_checked": validation_result.get("grants_checked", 0),
            "grants_updated": validation_result.get("grants_updated", 0),
            "timestamp": datetime.now(pytz.timezone('Asia/Kuala_Lumpur')).isoformat(),
            "project_id": JAMAIBASE_PROJECT_ID,
            "execution_time": "3am MYT Daily",
            "method": "sequential_scraping_with_validation"
        }
        
        if summary["success"]:
            logging.info(f"📊 Cron job completed successfully: {len(grant_entries)} new grants, {validation_result.get('grants_updated', 0)} grants updated")
        else:
            logging.error("❌ Cron job completed with errors")
        
        return summary
        
    except Exception as e:
        logging.error(f"❌ Web scraping failed: {e}")
        return {"success": False, "error": str(e)}


def setup_daily_cron():
    """Setup the daily cron job to run at 3am MYT"""
    # Schedule the job to run daily at 3am Malaysia Time
    schedule.every().day.at("03:00").do(cron_web_search)
    
    print("✅ Daily cron job scheduled:")
    print("   🕒 Time: 3:00 AM MYT (Asia/Kuala_Lumpur)")
    print("   🔄 Frequency: Every day")
    print("   📝 Task: Scrape and validate Malaysian grants")
    print("   🎯 Table: scrap_result")
    print("   📊 Column: grant_scrap")
    print("   🚫 Duplicate Prevention: ENABLED")
    print("\n🔄 Cron job is running... Press Ctrl+C to stop.")
    
    # Keep the script running
    while True:
        schedule.run_pending()
        time.sleep(60)  # Check every minute


if __name__ == "__main__":
    import sys
    
    # Command line argument handling
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == "cron":
            # Start the cron job scheduler
            print("🚀 Starting Daily Cron Job Scheduler...")
            setup_daily_cron()
            
        elif command == "run-now":
            # Run the job immediately
            print("🚀 Running Grant Scraping and Validation Immediately...")
            result = cron_web_search()
            print(f"📊 Result: {json.dumps(result, indent=2)}")
            
        else:
            print("Usage:")
            print("  python web_scraper_agent.py run-now  - Run scraping immediately")
            print("  python web_scraper_agent.py cron     - Start daily cron scheduler")
    else:
        # Default: run immediately
        print("🚀 Running Grant Scraping and Validation Immediately...")
        result = cron_web_search()
        print(f"📊 Result: {json.dumps(result, indent=2)}")