"""
NexusMCPServer Module
Handles the Model Context Protocol (MCP) layer for the NexusAgent architecture.
This class defines secure data-access methods, regex-based sanitization routines 
to prevent prompt injection, and business checks on project milestone completion.
"""

import re
import json
import logging
from typing import Dict, Any, Union

# Set up professional logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("NexusMCPServer")


class NexusMCPServer:
    """
    Decoupled Model Context Protocol Server for NexusAgent.
    Manages mock database state for projects and invoices, exposing validated 
    JSON-RPC methods for operations auditing and financial reconciliation.
    """

    def __init__(self) -> None:
        # Mock database storing project milestone details
        self._projects_db: Dict[str, Dict[str, Any]] = {
            "PRJ-001": {
                "project_id": "PRJ-001",
                "name": "Enterprise Cloud Migration",
                "milestone": "COMPLETED",
                "client": "Apex Corp",
                "manager": "Alice Vance",
                "budget": 150000.0,
            },
            "PRJ-002": {
                "project_id": "PRJ-002",
                "name": "AI Ledger Integration",
                "milestone": "IN_PROGRESS",
                "client": "Vertex Labs",
                "manager": "Bob Vance",
                "budget": 85000.0,
            }
        }

        # Mock database storing invoice ledgers
        self._invoices_db: Dict[str, Dict[str, Any]] = {
            "PRJ-001": {
                "invoice_id": "INV-1001",
                "amount": 15000.0,
                "reconciled": False,
                "audited": False,
                "audit_notes": ""
            },
            "PRJ-002": {
                "invoice_id": "INV-1002",
                "amount": 8500.0,
                "reconciled": False,
                "audited": False,
                "audit_notes": ""
            }
        }

        # Dict mapping string methods to actual Python callables, simulating a JSON-RPC routing table
        self._rpc_router: Dict[str, Any] = {
            "fetch_milestone_status": self.fetch_milestone_status,
            "generate_reconciled_invoice": self.generate_reconciled_invoice
        }

    def _sanitize_input(self, value: str) -> str:
        """
        Private security guardrail to prevent prompt injections, path traversal, or command injection.
        Strips any characters not matching alphanumeric, dashes, or underscores, and screens for 
        suspicious agent override keyword patterns.
        
        Args:
            value: The raw input string.
            
        Returns:
            A cleaned, safe alphanumeric-dashed string.
            
        Raises:
            ValueError: If the input contains known malicious agent control overrides.
        """
        if not isinstance(value, str):
            raise TypeError("Input value must be a string.")

        # Clean string spaces to inspect content
        trimmed = value.strip()

        # Security check: Scan for injection keywords attempting system role-play or instructions override
        injection_patterns = [
            r"(?i)\bignore\b.*\binstruction",
            r"(?i)\bsystem\b.*\bprompt",
            r"(?i)\bas\b.*\ba\b.*\bprincipal",
            r"(?i)\boverride\b"
        ]
        for pattern in injection_patterns:
            if re.search(pattern, trimmed):
                logger.error(f"Potential Prompt Injection detected in payload: '{trimmed}'")
                raise ValueError("Security violation: Malicious input structure detected.")

        # Regex Sanitization: Keep only letters, digits, dashes, and underscores
        sanitized = re.sub(r"[^a-zA-Z0-9_\-]", "", trimmed)
        
        if sanitized != trimmed:
            logger.warning(f"Input '{trimmed}' sanitized to '{sanitized}' due to illegal characters.")

        return sanitized

    def handle_json_rpc(self, request_json: str) -> str:
        """
        Receives, parses, and routes incoming JSON-RPC 2.0 requests to the correct internal method.
        Ensures proper handling and returns standard error responses.
        
        Args:
            request_json: A JSON-formatted string matching the JSON-RPC request format.
            
        Returns:
            A JSON-formatted string matching the JSON-RPC response format.
        """
        try:
            request = json.loads(request_json)
        except json.JSONDecodeError as exc:
            return json.dumps({
                "jsonrpc": "2.0",
                "error": {"code": -32700, "message": f"Parse error: {str(exc)}"},
                "id": None
            })

        req_id = request.get("id")
        method = request.get("method")
        params = request.get("params", {})

        # Ensure parameters are safely un-wrapped and validated
        if not method or method not in self._rpc_router:
            return json.dumps({
                "jsonrpc": "2.0",
                "error": {"code": -32601, "message": f"Method not found: '{method}'"},
                "id": req_id
            })

        try:
            # Execute the routed method dynamically passing the keyword parameters
            result = self._rpc_router[method](**params)
            return json.dumps({
                "jsonrpc": "2.0",
                "result": result,
                "id": req_id
            })
        except Exception as exc:
            logger.error(f"Error executing method '{method}': {str(exc)}")
            return json.dumps({
                "jsonrpc": "2.0",
                "error": {"code": -32000, "message": str(exc)},
                "id": req_id
            })

    def fetch_milestone_status(self, project_id: str) -> Dict[str, Any]:
        """
        Fetches the milestone completion status for a project.
        Sanitizes project_id input using regex to block injections.
        
        Args:
            project_id: Unique string identifier of the project (e.g. 'PRJ-001').
            
        Returns:
            A dictionary containing project status details.
            
        Raises:
            KeyError: If the project does not exist in the database.
        """
        safe_project_id = self._sanitize_input(project_id)
        logger.info(f"Method fetch_milestone_status invoked for project_id: {safe_project_id}")

        if safe_project_id not in self._projects_db:
            logger.error(f"Project ID {safe_project_id} not found in database.")
            raise KeyError(f"Project ID '{safe_project_id}' does not exist.")

        return self._projects_db[safe_project_id]

    def generate_reconciled_invoice(self, project_id: str) -> Dict[str, Any]:
        """
        Reconciles the invoice associated with the project.
        Intercepts the request and fails safely if the project milestone status 
        is not explicitly 'COMPLETED'.
        
        Args:
            project_id: Unique string identifier of the project.
            
        Returns:
            The updated invoice details with reconciliation flag set to True.
            
        Raises:
            ValueError: If the project status is not 'COMPLETED'.
            KeyError: If the invoice does not exist.
        """
        safe_project_id = self._sanitize_input(project_id)
        logger.info(f"Method generate_reconciled_invoice invoked for project_id: {safe_project_id}")

        # Check project database status first
        project_data = self.fetch_milestone_status(safe_project_id)
        milestone = project_data.get("milestone")

        # Core Safety Guardrail: Intercept request and fail safely
        if milestone != "COMPLETED":
            logger.error(f"Reconciliation blocked: Project {safe_project_id} is in status '{milestone}'.")
            raise PermissionError(
                f"Action Denied: Invoice reconciliation requires milestone status to be 'COMPLETED'. "
                f"Current status for {safe_project_id} is '{milestone}'."
            )

        if safe_project_id not in self._invoices_db:
            logger.error(f"Invoice for project ID {safe_project_id} not found in database.")
            raise KeyError(f"Invoice for Project ID '{safe_project_id}' does not exist.")

        # Reconcile invoice ledger
        invoice = self._invoices_db[safe_project_id]
        invoice["reconciled"] = True
        invoice["audited"] = True
        invoice["audit_notes"] = f"Audited and approved. Reconciled under status: {milestone}"

        logger.info(f"Invoice {invoice['invoice_id']} successfully reconciled for project {safe_project_id}")
        return invoice
