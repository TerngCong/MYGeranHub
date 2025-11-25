import json
from typing import Any, Dict, List, Optional

import httpx

from ..core.config import settings


class RowSkip(Exception):
    """Raised when a row should be skipped but still marked to avoid reprocessing."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


class RowFailure(Exception):
    """Raised when a row cannot be synced due to bad data."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


class GrantSyncService:
    def __init__(self) -> None:
        self.base_url = (settings.jamai_base_url or "").rstrip("/")
        self.project_id = settings.jamai_project_id
        self.api_key = settings.jamai_api_key
        self.scrap_table_id = settings.jamai_scrap_result_table_id
        self.grants_table_id = settings.jamai_grants_table_id
        self.sync_status_column = settings.jamai_knowledge_sync_status_column
        self.headers = {
            "Authorization": f"Bearer {self.api_key}" if self.api_key else "",
            "Content-Type": "application/json",
        }
        if self.project_id:
            self.headers["X-PROJECT-ID"] = self.project_id
        self._api_prefix = "/api/v2"

    def _ensure_configuration(self) -> None:
        missing: List[str] = []
        if not self.base_url:
            missing.append("JAMAI_BASE_URL")
        if not self.project_id:
            missing.append("JAMAI_PROJECT_ID")
        if not self.api_key:
            missing.append("JAMAI_API_KEY")
        if not self.scrap_table_id:
            missing.append("JAMAI_SCRAP_RESULT_TABLE_ID")
        if not self.grants_table_id:
            missing.append("JAMAI_GRANTS_TABLE_ID")

        if missing:
            raise RuntimeError(f"Missing JamAI configuration values: {', '.join(missing)}")

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        json_payload: Optional[Dict[str, Any]] = None,
        timeout: float = 30.0,
    ) -> Dict[str, Any]:
        url = self._compose_url(path)
        headers = self.headers

        if not headers.get("Authorization"):
            raise RuntimeError("JamAI API key is not configured")

        with httpx.Client(timeout=timeout) as client:
            response = client.request(method, url, headers=headers, params=params, json=json_payload)
            response.raise_for_status()
            if response.content:
                return response.json()
            return {}

    def _compose_url(self, path: str) -> str:
        base = self.base_url
        if not base:
            raise RuntimeError("JamAI base URL is not configured")

        normalized_path = path if path.startswith("/") else f"/{path}"
        if normalized_path.startswith("/api/"):
            return f"{base}{normalized_path}"

        if base.endswith("/api/v2") or base.endswith("/api/v2/"):
            return f"{base.rstrip('/')}{normalized_path}"

        return f"{base}{self._api_prefix}{normalized_path}"

    def sync_pending_grants(self, limit: int = 20) -> Dict[str, int]:
        """
        Fetches pending rows from the action table, pushes approved grants into the knowledge
        table, and marks the processed rows with the sync status.
        """
        self._ensure_configuration()
        limit = max(1, min(limit, 100))
        rows = self._list_pending_rows(limit=limit)

        summary = {
            "processed": len(rows),
            "synced": 0,
            "failed": 0,
            "skipped": 0,
        }
        updates: Dict[str, Dict[str, str]] = {}

        for row in rows:
            row_id = self._extract_row_id(row)
            try:
                payload = self._prepare_knowledge_payload(row)
            except RowSkip as skip_exc:
                summary["skipped"] += 1
                updates[row_id] = {
                    self.sync_status_column: self._truncate_status(f"skipped: {skip_exc.reason}")
                }
                continue
            except RowFailure as failure_exc:
                summary["failed"] += 1
                updates[row_id] = {
                    self.sync_status_column: self._truncate_status(f"failed: {failure_exc.reason}")
                }
                continue

            try:
                self._insert_knowledge_row(payload)
            except Exception as exc:  # noqa: BLE001 - surface upstream errors
                summary["failed"] += 1
                updates[row_id] = {
                    self.sync_status_column: self._truncate_status(f"failed: {exc}")
                }
                continue

            summary["synced"] += 1
            updates[row_id] = {self.sync_status_column: "synced"}

        if updates:
            self._update_action_rows(updates)

        return summary

    def _list_pending_rows(self, limit: int) -> List[Dict[str, Any]]:
        where_clause = (
            '"grant_final" IS NOT NULL AND '
            '"grant_decider" = \'proceed to knowledge table sync\' AND '
            f'("{self.sync_status_column}" IS NULL OR "{self.sync_status_column}" != \'synced\')'
        )

        params = {
            "table_id": self.scrap_table_id,
            "limit": limit,
            "where": where_clause,
        }

        data = self._request(
            "GET",
            "/gen_tables/action/rows/list",
            params=params,
        )
        return data.get("rows", [])

    def _extract_row_id(self, row: Dict[str, Any]) -> str:
        row_id = row.get("id") or row.get("row_id")
        if not row_id:
            raise RuntimeError("Row payload missing 'id'")
        return str(row_id)

    def _prepare_knowledge_payload(self, row: Dict[str, Any]) -> Dict[str, Optional[str]]:
        columns: Dict[str, Any] = row.get("columns", {})
        grant_final_raw = self._extract_column_value(columns, "grant_final")
        if grant_final_raw is None:
            raise RowFailure("grant_final is empty")

        if isinstance(grant_final_raw, str) and grant_final_raw.strip().lower() == "failed to verify":
            raise RowSkip("grant_final flagged as failed to verify")

        grant_data = self._coerce_json(grant_final_raw)
        if not isinstance(grant_data, dict) or not grant_data:
            raise RowFailure("grant_final is not valid JSON")

        payload = self._map_grant_to_knowledge_row(grant_data)
        missing = [field for field in ("grant_name", "grant_description") if not payload.get(field)]
        if missing:
            raise RowFailure(f"missing required fields: {', '.join(missing)}")

        return payload

    def _extract_column_value(self, columns: Dict[str, Any], column_name: str) -> Any:
        data = columns.get(column_name)
        if isinstance(data, dict):
            if "value" in data:
                return data["value"]
            if "text" in data:
                return data["text"]
            if "choices" in data:
                return data["choices"]
        return data

    def _coerce_json(self, value: Any) -> Any:
        if isinstance(value, dict):
            return value
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return None
            try:
                return json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise RowFailure(f"invalid JSON in grant_final: {exc}") from exc
        return value

    def _map_grant_to_knowledge_row(self, grant_data: Dict[str, Any]) -> Dict[str, Optional[str]]:
        application_process = grant_data.get("applicationProcess") or grant_data.get("application_process")
        required_documents_section = (
            grant_data.get("requiredDocuments")
            or (application_process or {}).get("requiredDocuments")
            or grant_data.get("documentRequired")
        )

        knowledge_row = {
            "grant_name": self._first_non_empty(
                self._extract_text(grant_data.get("grantName")),
                grant_data.get("grant_name"),
            ),
            "grant_period": self._first_non_empty(
                self._extract_text(grant_data.get("period")),
                grant_data.get("grant_period"),
            ),
            "grant_description": self._first_non_empty(
                self._extract_text(grant_data.get("grantDescription")),
                grant_data.get("grant_description"),
            ),
            "eligibility_criteria": self._first_non_empty(
                self._extract_text(grant_data.get("eligibilityCriteria")),
                self._extract_text(grant_data.get("eligibility_criteria")),
                self._extract_text((grant_data.get("grantDescription") or {}).get("eligibilityCriteria")),
            ),
            "application_steps": self._first_non_empty(
                self._extract_text((application_process or {}).get("steps")),
                self._extract_text(grant_data.get("application_steps")),
            ),
            "document_required": self._format_required_documents(required_documents_section),
        }

        return knowledge_row

    def _first_non_empty(self, *candidates: Optional[str]) -> Optional[str]:
        for candidate in candidates:
            normalized = self._normalize_text(candidate)
            if normalized:
                return normalized
        return None

    def _normalize_text(self, value: Any) -> Optional[str]:
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return str(value)
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        if isinstance(value, dict):
            for key in ("value", "text", "description", "range", "summary"):
                if key in value:
                    normalized = self._normalize_text(value[key])
                    if normalized:
                        return normalized
            return None
        if isinstance(value, list):
            normalized_items = [self._normalize_text(item) for item in value]
            normalized_items = [item for item in normalized_items if item]
            if normalized_items:
                return "\n".join(normalized_items)
        return None

    def _extract_text(self, node: Any) -> Optional[str]:
        if node is None:
            return None
        if isinstance(node, (str, int, float)):
            return self._normalize_text(node)
        if isinstance(node, dict):
            for key in ("description", "text", "value", "range"):
                if key in node:
                    text = self._normalize_text(node[key])
                    if text:
                        return text
            # If node itself has nested content like steps.files, collapse recursively.
            nested_values = [self._extract_text(value) for value in node.values()]
            nested_values = [value for value in nested_values if value]
            if nested_values:
                return "\n".join(nested_values)
            return None
        if isinstance(node, list):
            nested_values = [self._extract_text(item) for item in node]
            nested_values = [value for value in nested_values if value]
            if nested_values:
                return "\n".join(nested_values)
        return None

    def _format_required_documents(self, section: Any) -> Optional[str]:
        if not section:
            return None
        if isinstance(section, dict):
            files = section.get("files")
            if isinstance(files, list) and files:
                lines: List[str] = []
                for file in files:
                    if not isinstance(file, dict):
                        continue
                    name = self._normalize_text(file.get("name"))
                    link = self._normalize_text(file.get("downloadUrl") or file.get("sourceUrl"))
                    if name and link:
                        lines.append(f"{name} - {link}")
                    elif name:
                        lines.append(name)
                    elif link:
                        lines.append(link)
                if lines:
                    return "\n".join(lines)
        return self._extract_text(section)

    def _insert_knowledge_row(self, payload: Dict[str, Optional[str]]) -> None:
        json_payload = {
            "table_id": self.grants_table_id,
            "data": [payload],
            "stream": False,
            "concurrent": False,
        }
        self._request(
            "POST",
            "/gen_tables/knowledge/rows/add",
            json_payload=json_payload,
            timeout=60.0,
        )

    def _update_action_rows(self, updates: Dict[str, Dict[str, str]]) -> None:
        if not updates:
            return
        json_payload = {
            "table_id": self.scrap_table_id,
            "data": updates,
        }
        self._request(
            "PATCH",
            "/gen_tables/action/rows",
            json_payload=json_payload,
        )

    def _truncate_status(self, value: str, limit: int = 200) -> str:
        return value if len(value) <= limit else f"{value[:limit-3]}..."


grant_sync_service = GrantSyncService()

