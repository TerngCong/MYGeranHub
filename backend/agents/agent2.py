import json
import logging
import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

import pytz
from dotenv import load_dotenv
from jamaibase import JamAI, types as t  # type: ignore[import-not-found]
from openai import OpenAI, OpenAIError  # type: ignore[import-not-found]

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "o4-mini")
JAMAI_PROJECT_ID = (
    os.getenv("JAMAI_SDK_PROJECT_ID")
    or os.getenv("JAMAI_PROJECT_ID")
    or os.getenv("JAMAIBASE_PROJECT_ID")
)
JAMAI_TOKEN = (
    os.getenv("JAMAI_SDK_TOKEN")
    or os.getenv("JAMAI_API_KEY")
    or os.getenv("JAMAIBASE_API_KEY")
    or os.getenv("JAMAI_PAT")
)
TABLE_ID = os.getenv("JAMAI_SCRAP_RESULT_TABLE_ID", "scrap_result")
DEFAULT_LIMIT = 20

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(pytz.timezone("Asia/Kuala_Lumpur")).isoformat()


@dataclass
class VerificationRunSummary:
    success: bool
    started_at: str
    finished_at: str
    processed: int = 0
    updated_verified: int = 0
    updated_final: int = 0
    skipped: int = 0
    failed: int = 0
    row_ids: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

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
            "duration_seconds": self.duration_seconds,
            "processed": self.processed,
            "updated_verified": self.updated_verified,
            "updated_final": self.updated_final,
            "skipped": self.skipped,
            "failed": self.failed,
            "row_ids": self.row_ids,
            "errors": self.errors,
        }


class GrantVerificationAgent:
    """Agent 2: verifies scraped grants, corrects them, and writes back to JamAI."""

    def __init__(
        self,
        openai_api_key: Optional[str],
        jamai_project_id: Optional[str],
        jamai_token: Optional[str],
        table_id: str = TABLE_ID,
        model_name: str = OPENAI_MODEL,
    ) -> None:
        self.openai_api_key = openai_api_key
        self.model_name = model_name or OPENAI_MODEL
        self.table_id = table_id or TABLE_ID
        self.openai_client: Optional[OpenAI] = (
            OpenAI(api_key=openai_api_key) if openai_api_key else None
        )
        self.jamai_client: Optional[JamAI] = (
            JamAI(project_id=jamai_project_id, token=jamai_token)
            if jamai_project_id and jamai_token
            else None
        )

    def run(
        self,
        *,
        row_ids: Optional[List[str]] = None,
        limit: Optional[int] = None,
    ) -> VerificationRunSummary:
        started_at = _now_iso()
        if not self.openai_client:
            return VerificationRunSummary(
                success=False,
                started_at=started_at,
                finished_at=_now_iso(),
                errors=["OPENAI_API_KEY not configured"],
            )

        if not self.jamai_client:
            return VerificationRunSummary(
                success=False,
                started_at=started_at,
                finished_at=_now_iso(),
                errors=["JamAI credentials not configured"],
            )

        rows = self._list_target_rows(row_ids=row_ids, limit=limit or DEFAULT_LIMIT)
        summary = VerificationRunSummary(
            success=True,
            started_at=started_at,
            finished_at=started_at,
        )

        for raw_row in rows:
            normalized = self._normalize_row(raw_row)
            row_id = normalized.get("id")
            if not row_id:
                summary.skipped += 1
                continue
            summary.row_ids.append(row_id)

            columns = normalized.get("columns", {})
            grant_final = self._extract_column_value(columns, "grant_final")
            if isinstance(grant_final, str) and grant_final.strip():
                summary.skipped += 1
                continue

            grant_scrap_raw = self._extract_column_value(columns, "grant_scrap")
            grant_scrap = self._coerce_json(grant_scrap_raw)
            if not isinstance(grant_scrap, dict):
                summary.skipped += 1
                summary.errors.append(f"{row_id}: grant_scrap missing or invalid")
                continue

            try:
                verification_result = self._process_input(grant_scrap)
                verified_payload = self._normalize_json_string(verification_result)
                self._update_columns(row_id, {"grant_verified": verified_payload})
                summary.updated_verified += 1

                final_payload = self._produce_final_payload(
                    row_id, grant_scrap, verification_result
                )
                self._update_columns(row_id, {"grant_final": final_payload})
                summary.updated_final += 1
                summary.processed += 1
            except Exception as exc:  # noqa: BLE001
                logger.exception("Grant verification failed for row %s: %s", row_id, exc)
                summary.failed += 1
                summary.errors.append(f"{row_id}: {exc}")

        summary.finished_at = _now_iso()
        summary.success = summary.failed == 0
        return summary

    def _list_target_rows(
        self,
        *,
        row_ids: Optional[List[str]],
        limit: Optional[int],
    ) -> List[Dict[str, Any]]:
        if not self.jamai_client:
            return []

        if row_ids:
            rows: List[Dict[str, Any]] = []
            for row_id in row_ids:
                try:
                    response = self.jamai_client.table.get_table_row(
                        table_type="action",
                        table_id=self.table_id,
                        row_id=row_id,
                    )
                except Exception as exc:  # noqa: BLE001
                    logger.error("Failed to fetch row %s: %s", row_id, exc)
                    continue
                items = self._extract_items(response)
                if items:
                    rows.append(self._row_to_dict(items[0]))
            return rows

        try:
            response = self.jamai_client.table.list_table_rows("action", self.table_id)
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to list action table rows: %s", exc)
            return []

        raw_rows = self._extract_items(response)

        if not isinstance(raw_rows, list):
            return []

        if limit:
            raw_rows = raw_rows[:limit]

        return [self._row_to_dict(row) for row in raw_rows]

    def _row_to_dict(self, row: Any) -> Dict[str, Any]:
        if isinstance(row, dict):
            return row
        if hasattr(row, "model_dump"):
            return row.model_dump()  # type: ignore[attr-defined]
        if hasattr(row, "__dict__"):
            return dict(row.__dict__)
        return {}

    def _extract_items(self, response: Any) -> Optional[List[Any]]:
        """Handle JamAI SDK responses where `items` might be an attribute, a method, or a dict key."""
        if response is None:
            return None

        items_attr = getattr(response, "items", None)
        if callable(items_attr):
            try:
                items_value = items_attr()
                if isinstance(items_value, list):
                    return items_value
            except TypeError:
                pass
        elif isinstance(items_attr, list):
            return items_attr

        if isinstance(response, dict):
            items_value = response.get("items")
            if isinstance(items_value, list):
                return items_value

        return None

    def _normalize_row(self, row: Dict[str, Any]) -> Dict[str, Any]:
        row_id = row.get("id") or row.get("ID") or row.get("row_id")
        columns = row.get("columns")
        if columns is None:
            columns = {
                key: value
                for key, value in row.items()
                if key not in {"id", "ID", "row_id", "updated_at", "Updated at"}
            }
        return {"id": str(row_id) if row_id else None, "columns": columns or {}}

    def _extract_column_value(self, columns: Dict[str, Any], column_name: str) -> Any:
        data = columns.get(column_name)
        if isinstance(data, dict):
            for key in ("value", "text", "description", "range", "json"):
                if key in data:
                    return data[key]
        return data

    def _coerce_json(self, value: Any) -> Any:
        if isinstance(value, dict):
            return value
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return None
            return json.loads(stripped)
        return value

    def _verify_claim(self, claim: Optional[str], url: Optional[str]) -> Dict[str, Any]:
        if not claim:
            return {
                "is_accurate": "unknown",
                "explanation": "missing claim text",
                "evidence": [],
            }
        if not url:
            return {
                "is_accurate": "unknown",
                "explanation": "missing source URL",
                "evidence": [],
            }

        prompt = f"""
You are a grant fact-checker. Verify the following grant detail using ONLY information from the URL.

URL: {url}

Claim to verify:
{claim}

Return ONLY a JSON object with these exact fields:
 - "is_accurate": true/false/unknown,
 - "explanation": "text",
 - "evidence": ["list", "of", "quotes"]

Remember:
- Output ONLY valid JSON
- Never add commentary
- Never add markdown
- Never add backticks
"""
        response_text = self._call_openai_chat(
            system_prompt=(
                "You are a grant fact-checking AI. Output strictly valid JSON with "
                "the keys is_accurate, explanation, and evidence."
            ),
            user_prompt=prompt,
        )
        try:
            return json.loads(response_text)
        except json.JSONDecodeError as exc:
            logger.warning("Failed to parse verification JSON: %s", exc)
            return {
                "is_accurate": "unknown",
                "explanation": "model returned invalid JSON",
                "evidence": [],
            }

    def _process_input(self, data: Dict[str, Any]) -> Dict[str, Any]:
        results: Dict[str, Any] = {}

        grant_name = data.get("grantName") or {}
        if grant_name:
            results["grantName"] = self._verify_claim(
                grant_name.get("value"), grant_name.get("sourceUrl")
            )

        period = data.get("period") or {}
        if period:
            results["period"] = self._verify_claim(
                period.get("range"), period.get("sourceUrl")
            )

        description = data.get("grantDescription") or {}
        if description:
            results["grantDescription"] = self._verify_claim(
                description.get("text"), description.get("sourceUrl")
            )

        application_process = data.get("applicationProcess") or {}
        if application_process:
            app_result: Dict[str, Any] = {}
            steps = application_process.get("steps") or {}
            if steps:
                app_result["steps"] = self._verify_claim(
                    steps.get("description"), steps.get("sourceUrl")
                )

            required_documents = application_process.get("requiredDocuments") or {}
            doc_results: List[Dict[str, Any]] = []
            for file_info in required_documents.get("files", []) or []:
                doc_results.append(
                    self._verify_claim(
                        f"Document required: {file_info.get('name')}",
                        file_info.get("sourceUrl"),
                    )
                )
            if doc_results:
                app_result["requiredDocuments"] = doc_results

            if app_result:
                results["applicationProcess"] = app_result

        required_documents = data.get("requiredDocuments")
        if required_documents and "requiredDocuments" not in results:
            doc_results = []
            for file_info in required_documents.get("files", []) or []:
                doc_results.append(
                    self._verify_claim(
                        f"Document required: {file_info.get('name')}",
                        file_info.get("sourceUrl"),
                    )
                )
            if doc_results:
                results["requiredDocuments"] = doc_results

        return results

    def _normalize_json_string(self, payload: Any) -> str:
        return json.dumps(payload, separators=(",", ":"), ensure_ascii=False)

    def _update_columns(self, row_id: str, data: Dict[str, str]) -> None:
        if not self.jamai_client:
            raise RuntimeError("JamAI client not initialized")
        self.jamai_client.table.update_table_rows(
            "action",
            t.MultiRowUpdateRequest(
                table_id=self.table_id,
                data={row_id: data},
            ),
        )

    def _produce_final_payload(
        self,
        row_id: str,
        original: Dict[str, Any],
        verification_result: Dict[str, Any],
    ) -> str:
        prompt = f"""
You are a professional grant fact-checking AI. You receive:

1. The original extracted grant detail JSON: {json.dumps(original, ensure_ascii=False)}
2. The verification result JSON: {json.dumps(verification_result, ensure_ascii=False)}

Instructions:
- If all verify_json.is_accurate values are true, return ONLY the original JSON object.
- Otherwise, perform external verification, rebuild a corrected grant JSON with the exact fields:
  grantName, period, grantDescription, applicationProcess (steps + requiredDocuments).
- If you are NOT fully confident after corrections, return the exact string failed to verify.
- Output must be either a valid JSON object or failed to verify. No markdown, no explanations.
"""
        response_text = self._call_openai_chat(
            system_prompt=(
                "You are a grant fact-checking AI. Return either a valid JSON object "
                "matching the required schema or the string failed to verify."
            ),
            user_prompt=prompt,
        )
        parsed = self._parse_model_output(response_text)
        if isinstance(parsed, dict) and self._is_valid_final_payload(parsed):
            return self._normalize_json_string(parsed)

        if isinstance(parsed, str):
            if parsed.strip().lower() == "failed to verify":
                return "failed to verify"

        logger.warning("Grant final output invalid for row %s, defaulting to failure", row_id)
        return "failed to verify"

    def _call_openai_chat(self, system_prompt: str, user_prompt: str) -> str:
        if not self.openai_client:
            raise RuntimeError("OpenAI client not initialized")
        try:
            response = self.openai_client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )
        except OpenAIError as exc:  # noqa: PERF203
            raise RuntimeError(f"OpenAI request failed: {exc}") from exc

        content = response.choices[0].message.content or ""
        return content.strip()

    def _parse_model_output(self, raw_text: Optional[str]) -> Any:
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
                candidate_clean = (
                    candidate.replace("“", '"').replace("”", '"').replace("’", "'")
                )
                candidate_clean = re.sub(r",\s*(\}|])", r"\1", candidate_clean)
                try:
                    return json.loads(candidate_clean)
                except json.JSONDecodeError:
                    pass

        return text

    def _is_valid_final_payload(self, grant: Dict[str, Any]) -> bool:
        try:
            required_structure = {
                "grantName": ["value", "sourceUrl"],
                "period": ["range", "sourceUrl"],
                "grantDescription": ["text", "sourceUrl"],
                "applicationProcess": {
                    "steps": ["description", "sourceUrl"],
                    "requiredDocuments": ["sourceUrl", "files"],
                },
            }
            for key, fields in required_structure.items():
                if key not in grant:
                    return False
                if isinstance(fields, list):
                    if not all(field in grant[key] for field in fields):
                        return False
            app_process = grant["applicationProcess"]
            if not all(
                field in app_process["steps"]
                for field in required_structure["applicationProcess"]["steps"]
            ):
                return False
            req_docs = app_process["requiredDocuments"]
            if not all(
                field in req_docs
                for field in required_structure["applicationProcess"]["requiredDocuments"]
            ):
                return False
            if "files" in req_docs and isinstance(req_docs["files"], list):
                for file_item in req_docs["files"]:
                    if not all(key in file_item for key in ["name", "downloadUrl", "sourceUrl"]):
                        return False
            return True
        except Exception:
            return False


def run_grant_verifier(
    *,
    row_ids: Optional[List[str]] = None,
    limit: Optional[int] = None,
) -> VerificationRunSummary:
    agent = GrantVerificationAgent(
        openai_api_key=OPENAI_API_KEY,
        jamai_project_id=JAMAI_PROJECT_ID,
        jamai_token=JAMAI_TOKEN,
        table_id=TABLE_ID,
    )
    return agent.run(row_ids=row_ids, limit=limit)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )
    summary = run_grant_verifier()
    print(json.dumps(summary.to_dict(), indent=2, ensure_ascii=False))

