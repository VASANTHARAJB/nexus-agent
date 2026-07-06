"""
NexusAgent Agents Module
Houses the Google ADK multi-agent architecture and isolated actor handoff patterns.
Defines the OperationsAgent and FinancialAgent, which collaborate to validate and
reconcile financial records only after rigorous operational verification has succeeded.
"""

import time
import logging
from dataclasses import dataclass, asdict
from typing import Dict, Any, Optional
from nexus_agent.mcp_server import NexusMCPServer

# Initialize logging matching the execution driver format
logger = logging.getLogger("NexusAgents")


@dataclass
class ValidationPayload:
    """
    Structured validation payload containing audited project data.
    Acts as the secure, validated boundary contract passed during the actor handoff.
    """
    project_id: str
    project_name: str
    milestone_status: str
    budget: float
    audited_by: str
    validation_timestamp: float
    auth_token: str


class FinancialAgent:
    """
    FinancialAgent (Ledger modifications and reconciliation).
    Responsible for reconciling invoices and updating financial ledgers,
    but only executes when invoked via a secure, validated handoff payload.
    """

    def __init__(self, mcp_server: NexusMCPServer) -> None:
        self.mcp_server = mcp_server
        self.agent_name = "FinancialAgent"

    def receive_handoff(self, payload: ValidationPayload) -> Dict[str, Any]:
        """
        Receives an operational validation payload from the OperationsAgent.
        Performs structural verification and triggers the final financial ledger reconciliation.
        
        Args:
            payload: ValidationPayload passed from the OperationsAgent.
            
        Returns:
            A dictionary containing execution results and ledger update status.
        """
        logger.info(f"[{self.agent_name}] Handoff received. Verifying validation contract...")
        
        # Security validation of the handoff structure
        if not isinstance(payload, ValidationPayload):
            raise TypeError(f"[{self.agent_name}] Invalid handoff payload: Must be of type ValidationPayload.")

        # Simulate signature / authentication verification
        expected_token = f"SECURE-AUTH-{payload.project_id}-{payload.milestone_status}"
        if payload.auth_token != expected_token:
            logger.error(f"[{self.agent_name}] Cryptographic validation token mismatch. Blocked execution.")
            raise ValueError(f"[{self.agent_name}] Handoff payload authorization token is invalid.")

        logger.info(f"[{self.agent_name}] Handoff payload verified. Project {payload.project_id} budget: ${payload.budget}")
        logger.info(f"[{self.agent_name}] Triggering invoice reconciliation via MCP server...")

        # Request reconciliation from the MCP server
        try:
            invoice_result = self.mcp_server.generate_reconciled_invoice(payload.project_id)
            logger.info(f"[{self.agent_name}] Ledger successfully updated. Invoice Reconciled.")
            
            return {
                "status": "SUCCESS",
                "reconciled_invoice": invoice_result,
                "audited_by": payload.audited_by,
                "processed_at": time.time(),
                "telemetry": {
                    "handoff_latency_sec": time.time() - payload.validation_timestamp,
                    "agent_transition": "OperationsAgent -> FinancialAgent"
                }
            }
        except Exception as exc:
            logger.error(f"[{self.agent_name}] Failed to update ledger or reconcile invoice: {str(exc)}")
            raise exc


class OperationsAgent:
    """
    OperationsAgent (Operational deliverable auditing).
    Responsible for fetching project status from the MCP server, performing business audits,
    and handling the secure execution handoff to the FinancialAgent.
    """

    def __init__(self, mcp_server: NexusMCPServer, financial_agent: FinancialAgent) -> None:
        self.mcp_server = mcp_server
        self.financial_agent = financial_agent
        self.agent_name = "OperationsAgent"

    def audit_project(self, project_id: str) -> Dict[str, Any]:
        """
        Audits a project's operational deliverables. If the project meets the completed
        milestone requirements, constructs a ValidationPayload and transfers control to FinancialAgent.
        
        Args:
            project_id: Unique identifier for the project to audit.
            
        Returns:
            A dictionary containing the audit summary and final reconciliation results.
        """
        logger.info(f"[{self.agent_name}] Beginning operations audit for project: {project_id}")

        # Fetch status using the MCP server context tool
        try:
            project_status = self.mcp_server.fetch_milestone_status(project_id)
        except Exception as exc:
            logger.error(f"[{self.agent_name}] Failed to fetch project status from MCP layer: {str(exc)}")
            raise exc

        milestone = project_status.get("milestone")
        logger.info(f"[{self.agent_name}] Project status retrieved. Milestone: '{milestone}'")

        # Business logic validation: Check if milestone criteria are met
        if milestone != "COMPLETED":
            logger.warning(
                f"[{self.agent_name}] Audit failed for project {project_id}. "
                f"Status is '{milestone}', which does not satisfy the 'COMPLETED' rule."
            )
            return {
                "status": "BLOCKED",
                "reason": f"Project milestone '{milestone}' is not completed.",
                "project_id": project_id,
                "audited_by": self.agent_name,
                "telemetry": {
                    "agent_transition": "OperationsAgent (Terminated safely)"
                }
            }

        logger.info(f"[{self.agent_name}] Milestone status validated. Preparing secure handoff contract...")

        # Construct safe auth token to represent validation credentials
        auth_token = f"SECURE-AUTH-{project_id}-{milestone}"

        # Build validation payload to transition between actors
        payload = ValidationPayload(
            project_id=project_id,
            project_name=project_status.get("name", "Unknown Project"),
            milestone_status=milestone,
            budget=project_status.get("budget", 0.0),
            audited_by=self.agent_name,
            validation_timestamp=time.time(),
            auth_token=auth_token
        )

        logger.info(f"[{self.agent_name}] Operational validation succeeded. Handoff to Financial Agent initiated.")

        # Execute safe actor handoff
        try:
            reconciliation_response = self.financial_agent.receive_handoff(payload)
            return {
                "status": "APPROVED",
                "reconciliation_details": reconciliation_response,
                "project_details": project_status
            }
        except Exception as exc:
            logger.error(f"[{self.agent_name}] Error during financial handoff execution: {str(exc)}")
            raise exc
