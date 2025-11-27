# agents/web_scraper_agent.py
import google.generativeai as genai
from jamaibase import JamAI, types as t  # type: ignore[import-not-found]
from typing import Any, Dict, List, Optional, Set
from dotenv import load_dotenv
import json
import re
import os
from datetime import datetime
import logging
import time
from dataclasses import dataclass, field
import uuid
import schedule  # type: ignore[import-not-found]
import pytz

# Load environment variables
# Load environment variables
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
# Support both the historical JAMAIBASE_* keys and the unified JAMAI_* keys
JAMAIBASE_PROJECT_ID = (
    os.getenv("JAMAI_SDK_PROJECT_ID")
    or os.getenv("JAMAI_PROJECT_ID")
    or os.getenv("JAMAIBASE_PROJECT_ID")
)
JAMAIBASE_API_KEY = (
    os.getenv("JAMAI_SDK_TOKEN")
    or os.getenv("JAMAI_API_KEY")
    or os.getenv("JAMAIBASE_API_KEY")
    or os.getenv("JAMAI_PAT")
)
SCRAP_TABLE_ID = os.getenv("JAMAI_SCRAP_RESULT_TABLE_ID", "scrap_result")

# Initialize JamAI client globally (fallback for CLI usage)
jamai = None
if JAMAIBASE_PROJECT_ID and JAMAIBASE_API_KEY:
    jamai = JamAI(project_id=JAMAIBASE_PROJECT_ID, token=JAMAIBASE_API_KEY)

@dataclass
class GrantEntry:
    """Structure for grant entries in JamAIBase scrap_result Table"""
    id: str
    grant_scrap: str  # Store as JSON string for the table
    updated_at: str
    status: str = "active"

@dataclass
class ScraperRunSummary:
    """Structured summary for orchestrators and logs."""

    success: bool
    started_at: str
    finished_at: str
    grants_requested: int
    grants_scraped: int
    grants_added: int
    grants_updated: int
    processed_row_ids: List[str] = field(default_factory=list)
    skipped_existing: List[str] = field(default_factory=list)
    failed_grants: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    project_id: Optional[str] = None
    method: str = "sequential_scraping_with_selective_updates"

    @property
    def duration_seconds(self) -> float:
        try:
            start_dt = datetime.fromisoformat(self.started_at)
            end_dt = datetime.fromisoformat(self.finished_at)
            return max(0.0, (end_dt - start_dt).total_seconds())
        except Exception:
            return 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "timestamp": self.finished_at,
            "duration_seconds": self.duration_seconds,
            "grants_requested": self.grants_requested,
            "grants_found": self.grants_requested,
            "grants_scraped": self.grants_scraped,
            "grants_added": self.grants_added,
            "grants_updated": self.grants_updated,
            "processed_row_ids": self.processed_row_ids,
            "skipped_existing": self.skipped_existing,
            "failed_grants": self.failed_grants,
            "errors": self.errors,
            "project_id": self.project_id,
            "method": self.method,
        }


def _now_iso() -> str:
    return datetime.now(pytz.timezone("Asia/Kuala_Lumpur")).isoformat()


class WebScraperAgent:
    """Agent 1: Performs reliable sequential web scraping"""
    
    def __init__(self, gemini_api_key: str, jamai_client, model_name: Optional[str] = None):
        self.gemini_api_key = gemini_api_key
        self.jamai_client = jamai_client
        self.model = None
        self.model_name = model_name or "gemini-2.0-flash"
        self.grant_entries: List[GrantEntry] = []
        self.skipped_existing: List[str] = []
        self.failed_grants: List[str] = []
        self.processed_grant_names: List[str] = []
        self.errors: List[str] = []
        self.requested_grant_count: int = 0
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

    def scrape_all_grants(
        self,
        existing_grant_names: Optional[Set[str]] = None,
        max_candidates: Optional[int] = None,
    ) -> List[GrantEntry]:
        """
        Main method: Simple sequential scraping with limit to save quota.
        Optionally skips grants that are already present in the JamAI action table.
        """
        # Reset run stats
        self.grant_entries = []
        self.skipped_existing = []
        self.failed_grants = []
        self.processed_grant_names = []
        self.errors = []
        self.requested_grant_count = 0

        if not self.model:
            logging.error("❌ AI model not available for web search")
            return []
        
        try:
            logging.info("🔍 Starting web search for Malaysian grants...")
            
            # Step 1: Get comprehensive list of grant names (limited to save quota)
            grant_names = self._get_comprehensive_grant_list(max_candidates=max_candidates)
            self.requested_grant_count = len(grant_names)
            
            if not grant_names:
                logging.error("❌ No grant names found to scrape")
                return []
            
            if existing_grant_names:
                filtered_names: List[str] = []
                for grant_name in grant_names:
                    normalized = grant_name.strip().lower()
                    if normalized in existing_grant_names:
                        self.skipped_existing.append(grant_name)
                        continue
                    filtered_names.append(grant_name)
                grant_names = filtered_names

            if not grant_names:
                logging.info("📭 All grant names were skipped because they already exist in the table.")
                return []

            logging.info(f"📋 Found {len(grant_names)} grants for processing")
            
            # Step 2: Sequential scraping for all grants
            scraped_grants = self._sequential_scraping(grant_names)
            
            # Step 3: Convert to grant entries
            grant_entries = self._create_grant_entries(scraped_grants)
            
            logging.info(f"✅ Web search completed. Found {len(grant_entries)} grants")
            return grant_entries
            
        except Exception as e:
            logging.error(f"❌ Web search failed: {e}")
            self.errors.append(str(e))
            return []

    def _get_comprehensive_grant_list(self, max_candidates: Optional[int] = None) -> List[str]:
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
            limit = max(1, min(max_candidates or 10, 25))
            return grant_names[:limit]
            
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
                    self.processed_grant_names.append(grant_name)
                    logging.info(f"✅ Successfully scraped: {grant_name}")
                else:
                    failure_reason = "invalid structure" if grant_data else "no data returned"
                    self.failed_grants.append(f"{grant_name} - {failure_reason}")
                    logging.warning(f"⚠️ Failed to scrape valid data for: {grant_name}")
                
                # Add delay to avoid rate limiting
                time.sleep(2)  # Reduced delay to 2 seconds
                
            except Exception as e:
                logging.error(f"❌ Error scraping {grant_name}: {e}")
                self.failed_grants.append(f"{grant_name} - exception: {e}")
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
                    wait_time = min(120, 15 * (2 ** attempt))
                    logging.warning(f"⚠️ Quota limit hit, waiting {wait_time} seconds... (attempt {attempt + 1})")
                    time.sleep(wait_time)
                    continue
                else:
                    logging.error(f"❌ AI request error: {e}")
                    self.errors.append(str(e))
                    return None
        logging.error("❌ All retries failed due to quota limits")
        self.errors.append("quota limit reached")
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
    
    def __init__(
        self,
        project_id: Optional[str] = None,
        token: Optional[str] = None,
        table_id: Optional[str] = None,
    ):
        pid = project_id or JAMAIBASE_PROJECT_ID
        tok = token or JAMAIBASE_API_KEY
        self.table_id = table_id or SCRAP_TABLE_ID
        if pid and tok:
            self.client = JamAI(project_id=pid, token=tok)
        else:
            self.client = jamai
    
    def add_or_update_grant_entries(self, grant_entries: List[GrantEntry]) -> Dict[str, Any]:
        """
        Add or update grant entries in JamAIBase scrap_result table
        Only deletes and replaces existing grants, keeps other grants intact
        """
        if not self.client:
            logging.error("❌ JamAI client not initialized")
            return {"success": False, "added": 0, "updated": 0, "processed_ids": []}
            
        try:
            # Step 1: Get all existing grants
            existing_grants = self.get_grants_from_table()
            existing_grant_map = {}  # Map grant name to grant info
            
            for grant in existing_grants:
                grant_data = grant.get("grant_scrap", {})
                grant_name = grant_data.get("grantName", {}).get("value", "").strip()
                if grant_name:
                    existing_grant_map[grant_name.lower()] = grant
            
            logging.info(f"📊 Found {len(existing_grant_map)} existing grants in table")
            
            # Step 2: Identify which grants need to be updated vs added
            grants_to_delete = []  # Existing grants that need to be replaced
            grants_to_add = []     # New grants to add
            updated_count = 0
            
            for entry in grant_entries:
                grant_data = json.loads(entry.grant_scrap)
                grant_name = grant_data.get("grantName", {}).get("value", "").strip()
                
                if not grant_name:
                    logging.warning(f"⚠️ Skipping entry with empty grant name: {entry.id}")
                    continue
                
                if grant_name.lower() in existing_grant_map:
                    # This grant already exists, mark the old one for deletion
                    existing_grant = existing_grant_map[grant_name.lower()]
                    grants_to_delete.append(existing_grant["id"])
                    grants_to_add.append(entry)  # Add the new version
                    updated_count += 1
                    logging.info(f"🔄 Will replace existing grant: {grant_name}")
                else:
                    # This is a new grant
                    grants_to_add.append(entry)
                    logging.info(f"✅ Will add new grant: {grant_name}")
            
            # Step 3: Delete only the existing grants that need to be replaced
            if grants_to_delete:
                logging.info(f"🗑️ Deleting {len(grants_to_delete)} existing grants to be replaced...")
                delete_success = self._delete_specific_grants(grants_to_delete)
                if not delete_success:
                    logging.error("❌ Failed to delete existing grants")
                    return {"success": False, "added": 0, "updated": 0}
            else:
                logging.info("📭 No existing grants to delete")
            
            # Step 4: Add all new and updated grants
            added_count = 0
            processed_ids: List[str] = []
            if grants_to_add:
                add_result = self._add_new_grants(grants_to_add)
                added_count = add_result["count"]
                processed_ids = add_result["row_ids"]
                logging.info(f"✅ Added {added_count} grants to table")

            logging.info(f"📊 Grant processing completed: {added_count} added, {updated_count} grants updated")
            return {
                "success": True,
                "added": added_count,
                "updated": updated_count,
                "total_processed": added_count,
                "processed_ids": processed_ids,
            }
                        
        except Exception as e:
            logging.error(f"❌ Error processing grants in JamAIBase: {e}")
            return {"success": False, "added": 0, "updated": 0, "processed_ids": []}

    def _delete_specific_grants(self, grant_ids: List[str]) -> bool:
        """Delete specific grants from the table by their IDs"""
        try:
            if not grant_ids:
                logging.info("📭 No grants to delete")
                return True
            
            logging.info(f"🗑️ Deleting {len(grant_ids)} specific grants...")
            
            # Delete specific rows
            response = self.client.table.delete_table_rows(
                "action",
                t.RowDeleteRequest(
                    table_id=self.table_id,
                    row_ids=grant_ids,
                ),
            )
            
            if response.ok:
                logging.info(f"✅ Successfully deleted {len(grant_ids)} grants")
                return True
            else:
                logging.error("❌ Failed to delete grants")
                return False
                
        except Exception as e:
            logging.error(f"❌ Error deleting specific grants: {e}")
            return False

    def _add_new_grants(self, grant_entries: List[GrantEntry]) -> Dict[str, Any]:
        """Add new grants to the table in batch"""
        try:
            rows_data = []
            for entry in grant_entries:
                row_data = {
                    "id": entry.id,
                    "updated_at": entry.updated_at,
                    "grant_scrap": entry.grant_scrap,
                    "status": entry.status
                }
                rows_data.append(row_data)
            
            completion = self.client.table.add_table_rows(
                "action",
                t.MultiRowAddRequest(
                    table_id=self.table_id,
                    data=rows_data,
                    stream=False
                ),
            )
            
            row_ids = self._extract_row_ids_from_completion(completion)
            added_count = len(row_ids) or len(rows_data)
            logging.info(f"✅ Added {added_count} grants to table")
            return {"count": added_count, "row_ids": row_ids}
                        
        except Exception as e:
            logging.error(f"❌ Error adding new grants: {e}")
            return {"count": 0, "row_ids": []}

    def get_grants_from_table(self) -> List[Dict]:
        """Get all grants from scrap_result table using proper SDK method"""
        if not self.client:
            logging.error("❌ JamAI client not initialized")
            return []
            
        try:
            # Use JamAIBase SDK method for listing rows - following documentation format
            rows = self.client.table.list_table_rows("action", self.table_id)
            
            grants = []
            items = getattr(rows, "items", None)
            if not items and isinstance(rows, dict):
                items = rows.get("items", [])

            # Paginated items - following documentation format
            for row in items or []:
                grant_scrap_data = self._parse_grant_scrap_cell(row.get("grant_scrap"))
                
                grant_info = {
                    "id": row.get("ID") or row.get("id") or row.get("row_id"),
                    "updated_at": row.get("updated_at", ""),
                    "grant_scrap": grant_scrap_data,
                    "status": row.get("status", "active")
                }
                grants.append(grant_info)
            
            logging.info(f"📋 Retrieved {len(grants)} grants from scrap_result table")
            return grants
            
        except Exception as e:
            logging.error(f"❌ Error getting grants from table: {e}")
            return []

    def find_grant_by_name(self, grant_name: str) -> Optional[Dict]:
        """Find an existing grant by name to avoid duplicates"""
        try:
            grants = self.get_grants_from_table()
            for grant in grants:
                grant_data = grant.get("grant_scrap", {})
                existing_name = grant_data.get("grantName", {}).get("value", "").strip()
                if existing_name and existing_name.lower() == grant_name.lower():
                    return grant
            return None
        except Exception as e:
            logging.error(f"❌ Error finding grant by name {grant_name}: {e}")
            return None

    def get_existing_grant_names(self) -> Set[str]:
        """Return a set of normalized grant names already stored in the table."""
        grant_names: Set[str] = set()
        for grant in self.get_grants_from_table():
            grant_data = grant.get("grant_scrap", {})
            grant_name_node = grant_data.get("grantName") or {}
            name = grant_name_node.get("value") if isinstance(grant_name_node, dict) else None
            normalized = name.strip().lower() if isinstance(name, str) else ""
            if normalized:
                grant_names.add(normalized)
        return grant_names

    def _parse_grant_scrap_cell(self, cell: Any) -> Dict[str, Any]:
        """Normalize JamAI cell payloads into the expected grant JSON dict."""
        if isinstance(cell, dict):
            if "grantName" in cell:
                return cell
            if "value" in cell:
                value = cell.get("value")
                if isinstance(value, str):
                    try:
                        return json.loads(value)
                    except json.JSONDecodeError:
                        logging.warning("⚠️ Failed to parse grant_scrap JSON string")
                        return {}
                if isinstance(value, dict):
                    return value
        if isinstance(cell, str):
            try:
                return json.loads(cell)
            except json.JSONDecodeError:
                logging.warning("⚠️ Failed to parse grant_scrap string")
                return {}
        return {}

    def _extract_row_ids_from_completion(self, completion: Any) -> List[str]:
        """Extract JamAI row IDs from add_table_rows responses."""
        row_ids: List[str] = []
        rows = getattr(completion, "rows", None)
        if rows is None and isinstance(completion, dict):
            rows = completion.get("rows")
        for row in rows or []:
            row_id = None
            if isinstance(row, dict):
                row_id = row.get("row_id") or row.get("id") or row.get("ID")
            else:
                row_id = getattr(row, "row_id", None) or getattr(row, "id", None)
            if row_id:
                row_ids.append(str(row_id))
        return row_ids


def run_scraper_job(
    *,
    gemini_api_key: Optional[str] = None,
    jamai_project_id: Optional[str] = None,
    jamai_token: Optional[str] = None,
    scrap_table_id: Optional[str] = None,
    skip_existing: bool = True,
    max_candidates: Optional[int] = None,
) -> ScraperRunSummary:
    """Execute the scraping flow and return a structured summary."""
    started_at = _now_iso()
    gemini_key = gemini_api_key or GEMINI_API_KEY
    jamai_project = jamai_project_id or JAMAIBASE_PROJECT_ID
    jamai_key = jamai_token or JAMAIBASE_API_KEY
    table_id = scrap_table_id or SCRAP_TABLE_ID

    if not gemini_key:
        errors = ["GEMINI_API_KEY not configured"]
        return ScraperRunSummary(
            success=False,
            started_at=started_at,
            finished_at=_now_iso(),
            grants_requested=0,
            grants_scraped=0,
            grants_added=0,
            grants_updated=0,
            processed_row_ids=[],
            skipped_existing=[],
            failed_grants=[],
            errors=errors,
            project_id=jamai_project,
        )

    if not jamai_project or not jamai_key:
        errors = ["JamAI credentials not configured"]
        return ScraperRunSummary(
            success=False,
            started_at=started_at,
            finished_at=_now_iso(),
            grants_requested=0,
            grants_scraped=0,
            grants_added=0,
            grants_updated=0,
            processed_row_ids=[],
            skipped_existing=[],
            failed_grants=[],
            errors=errors,
            project_id=jamai_project,
        )

    jamai_client = JamAIBaseClient(
        project_id=jamai_project,
        token=jamai_key,
        table_id=table_id,
    )

    web_scraper = WebScraperAgent(
        gemini_key,
        jamai_client,
    )

    existing_names = jamai_client.get_existing_grant_names() if skip_existing else None
    grant_entries = web_scraper.scrape_all_grants(
        existing_grant_names=existing_names,
        max_candidates=max_candidates,
    )

    result = {"success": True, "added": 0, "updated": 0, "processed_ids": []}
    if grant_entries:
        result = jamai_client.add_or_update_grant_entries(grant_entries)

    success = bool(result.get("success")) and not web_scraper.errors
    errors = list(web_scraper.errors)
    if not result.get("success"):
        errors.append("Failed to persist grant entries to JamAI")

    finished_at = _now_iso()
    return ScraperRunSummary(
        success=success,
        started_at=started_at,
        finished_at=finished_at,
        grants_requested=web_scraper.requested_grant_count,
        grants_scraped=len(web_scraper.processed_grant_names),
        grants_added=result.get("added", 0),
        grants_updated=result.get("updated", 0),
        processed_row_ids=result.get("processed_ids", []),
        skipped_existing=web_scraper.skipped_existing,
        failed_grants=web_scraper.failed_grants,
        errors=errors,
        project_id=jamai_project,
    )


# Cron Job Execution Function
def cron_web_search(skip_existing: bool = True, max_candidates: Optional[int] = None) -> Dict[str, Any]:
    """
    Main cron job function to be scheduled
    - Scrapes Malaysian grants using reliable sequential system
    - Adds or updates them in JamAIBase scrap_result table
    """
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('grant_scraper.log'),
            logging.StreamHandler()
        ]
    )
    summary = run_scraper_job(
        skip_existing=skip_existing,
        max_candidates=max_candidates,
    )

    if summary.success:
        logging.info(
            "📊 Cron job completed successfully: %s added, %s updated",
            summary.grants_added,
            summary.grants_updated,
        )
    else:
        logging.error("❌ Cron job completed with errors: %s", "; ".join(summary.errors) or "unknown error")
    return summary.to_dict()


def setup_daily_cron():
    """Setup the daily cron job to run at 3am MYT"""
    # Schedule the job to run daily at 3am Malaysia Time
    schedule.every().day.at("03:00").do(cron_web_search)
    
    print("✅ Daily cron job scheduled:")
    print("   🕒 Time: 3:00 AM MYT (Asia/Kuala_Lumpur)")
    print("   🔄 Frequency: Every day")
    print("   📝 Task: Scrape Malaysian grants")
    print("   🎯 Table: scrap_result")
    print("   📊 Column: grant_scrap")
    print("   🔄 Update Strategy: Replace existing grants, add new ones")
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
            print("🚀 Running Grant Scraping Immediately...")
            result = cron_web_search()
            print(f"📊 Result: {json.dumps(result, indent=2)}")
            
        else:
            print("Usage:")
            print("  python web_scraper_agent.py run-now  - Run scraping immediately")
            print("  python web_scraper_agent.py cron     - Start daily cron scheduler")
    else:
        # Default: run immediately
        print("🚀 Running Grant Scraping Immediately...")
        result = cron_web_search()
        print(f"📊 Result: {json.dumps(result, indent=2)}")