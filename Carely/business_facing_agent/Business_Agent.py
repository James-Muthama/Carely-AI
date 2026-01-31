"""
Multi-MCP Agent System
A comprehensive agent that orchestrates multiple MCP clients to execute complex user queries
through structured planning, execution, and evaluation pipeline.
"""

import logging
import json
import os
import time
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
from datetime import datetime, timezone
from urllib import request
from dotenv import load_dotenv, find_dotenv


# Load environment variables from .env file
load_dotenv(find_dotenv())

# Groq API Key
# Model API Keys
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

from flask import jsonify
# Import the existing MCP client and RAG components
from Carely.MCP_Client.Google_Workspace_MCP_Client_Class import GoogleWorkspaceMCPClient

logger = logging.getLogger(__name__)


class ExecutionType(Enum):
    READ_ONLY = "read_only"
    MODIFY = "modify"
    MIXED = "mixed"


class PlanStatus(Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXECUTED = "executed"
    FAILED = "failed"


@dataclass
class PlanStep:
    step_number: int
    description: str
    action_type: str  # 'read', 'write', 'update', 'delete', etc.
    mcp_client: str  # Which MCP client to use
    tool_name: str
    parameters: Dict[str, Any]
    expected_output: str
    dependencies: List[int] = None  # List of step numbers this depends on


@dataclass
class ExecutionPlan:
    plan_id: str
    user_query: str
    steps: List[PlanStep]
    execution_type: ExecutionType
    estimated_duration: float
    risk_level: str  # 'low', 'medium', 'high'
    status: PlanStatus
    created_at: datetime
    user_approval_required: bool = False


@dataclass
class ExecutionResult:
    step_number: int
    success: bool
    output: Any
    error: Optional[str] = None
    execution_time: float = 0.0


class MCPClientManager:
    """Manages multiple MCP clients"""

    def __init__(self):
        self.clients: Dict[str, Any] = {}

    def register_client(self, name: str, client: Any):
        """Register an MCP client"""
        self.clients[name] = client
        logger.info(f"Registered MCP client: {name}")

    def get_client(self, name: str) -> Any:
        """Get an MCP client by name"""
        return self.clients.get(name)

    def list_clients(self) -> List[str]:
        """List all registered clients"""
        return list(self.clients.keys())

    def health_check_all(self) -> Dict[str, bool]:
        """Check health of all registered clients"""
        health_status = {}
        for name, client in self.clients.items():
            try:
                if hasattr(client, 'connect'):
                    health_status[name] = client.connect()
                elif hasattr(client, 'health_check'):
                    health_status[name] = client.health_check()
                else:
                    health_status[name] = True  # Assume healthy if no method
            except Exception as e:
                logger.error(f"Health check failed for {name}: {e}")
                health_status[name] = False
        return health_status


class Planner:
    """
    Creates step-by-step execution plans for user queries using available MCP tools
    """

    def __init__(self, client_manager: MCPClientManager, llm_api_key: str):
        self.client_manager = client_manager
        self.llm_api_key = llm_api_key

    def create_plan(self, user_query: str) -> ExecutionPlan:
        """Create an execution plan for the user query"""
        try:
            # Get available tools from all clients
            available_tools = self._get_available_tools()

            # Use LLM to create plan
            plan_steps = self._generate_plan_steps(user_query, available_tools)

            # Analyze execution type
            execution_type = self._analyze_execution_type(plan_steps)

            # Create plan
            plan = ExecutionPlan(
                plan_id=f"plan_{int(time.time())}",
                user_query=user_query,
                steps=plan_steps,
                execution_type=execution_type,
                estimated_duration=self._estimate_duration(plan_steps),
                risk_level=self._assess_risk_level(plan_steps),
                status=PlanStatus.PENDING,
                created_at=datetime.now(timezone.utc),
                user_approval_required=(execution_type != ExecutionType.READ_ONLY)
            )

            logger.info(f"Created execution plan {plan.plan_id} with {len(plan_steps)} steps")
            return plan

        except Exception as e:
            logger.error(f"Failed to create plan: {e}")
            raise

    def _get_available_tools(self) -> Dict[str, List[Dict]]:
        """Get all available tools from registered MCP clients"""
        all_tools = {}

        for client_name, client in self.client_manager.clients.items():
            try:
                if hasattr(client, 'list_tools'):
                    tools = client.list_tools()
                    all_tools[client_name] = [
                        {
                            "name": tool.name,
                            "description": tool.description,
                            "input_schema": tool.inputSchema or {}
                        } for tool in tools
                    ]
                else:
                    logger.warning(f"Client {client_name} doesn't support list_tools()")
                    all_tools[client_name] = []
            except Exception as e:
                logger.error(f"Failed to get tools from {client_name}: {e}")
                all_tools[client_name] = []

        return all_tools

    def _generate_plan_steps(self, user_query: str, available_tools: Dict) -> List[PlanStep]:
        """Generate plan steps using LLM reasoning"""
        # This is a simplified version - in production, you'd use a proper LLM
        steps = []

        # For demonstration, create a simple heuristic-based planner
        query_lower = user_query.lower()

        # Example: Email-related queries
        if any(word in query_lower for word in ['email', 'mail', 'gmail', 'send']):
            if 'send' in query_lower:
                steps.append(PlanStep(
                    step_number=1,
                    description="Compose and send email",
                    action_type="write",
                    mcp_client="google_workspace",
                    tool_name="gmail_send",
                    parameters={"extract_from_query": user_query},
                    expected_output="Email sent confirmation"
                ))
            elif any(word in query_lower for word in ['search', 'find', 'look']):
                steps.append(PlanStep(
                    step_number=1,
                    description="Search emails",
                    action_type="read",
                    mcp_client="google_workspace",
                    tool_name="gmail_search",
                    parameters={"query": "is:inbox", "max_results": 10},
                    expected_output="List of matching emails"
                ))

        # Example: Calendar-related queries
        elif any(word in query_lower for word in ['calendar', 'meeting', 'appointment', 'schedule']):
            if any(word in query_lower for word in ['create', 'add', 'schedule']):
                steps.append(PlanStep(
                    step_number=1,
                    description="Create calendar event",
                    action_type="write",
                    mcp_client="google_workspace",
                    tool_name="calendar_create_event",
                    parameters={"extract_from_query": user_query},
                    expected_output="Event created confirmation"
                ))
            else:
                steps.append(PlanStep(
                    step_number=1,
                    description="List calendar events",
                    action_type="read",
                    mcp_client="google_workspace",
                    tool_name="calendar_list_events",
                    parameters={"time_max": "2024-12-31T23:59:59Z"},
                    expected_output="List of calendar events"
                ))

        # Example: Drive-related queries
        elif any(word in query_lower for word in ['drive', 'file', 'document', 'folder']):
            if any(word in query_lower for word in ['upload', 'create', 'add']):
                steps.append(PlanStep(
                    step_number=1,
                    description="Upload file to Drive",
                    action_type="write",
                    mcp_client="google_workspace",
                    tool_name="drive_upload",
                    parameters={"extract_from_query": user_query},
                    expected_output="File upload confirmation"
                ))
            else:
                steps.append(PlanStep(
                    step_number=1,
                    description="List Drive files",
                    action_type="read",
                    mcp_client="google_workspace",
                    tool_name="drive_list",
                    parameters={"max_results": 20},
                    expected_output="List of Drive files"
                ))

        # Default fallback
        else:
            steps.append(PlanStep(
                step_number=1,
                description="General information search",
                action_type="read",
                mcp_client="google_workspace",
                tool_name="search_web",
                parameters={"query": user_query},
                expected_output="Search results"
            ))

        return steps

    def _analyze_execution_type(self, steps: List[PlanStep]) -> ExecutionType:
        """Analyze if the plan only reads data or makes modifications"""
        read_actions = {'read', 'search', 'list', 'get', 'view'}
        write_actions = {'write', 'create', 'update', 'delete', 'send', 'upload'}

        has_read = any(step.action_type in read_actions for step in steps)
        has_write = any(step.action_type in write_actions for step in steps)

        if has_write and has_read:
            return ExecutionType.MIXED
        elif has_write:
            return ExecutionType.MODIFY
        else:
            return ExecutionType.READ_ONLY

    def _estimate_duration(self, steps: List[PlanStep]) -> float:
        """Estimate execution duration in seconds"""
        # Simple estimation based on action types
        duration_map = {
            'read': 2.0,
            'write': 5.0,
            'create': 3.0,
            'update': 4.0,
            'delete': 2.0,
            'send': 6.0,
            'upload': 10.0
        }

        total_duration = sum(duration_map.get(step.action_type, 3.0) for step in steps)
        return total_duration

    def _assess_risk_level(self, steps: List[PlanStep]) -> str:
        """Assess risk level of the execution plan"""
        high_risk_actions = {'delete', 'update'}
        medium_risk_actions = {'create', 'send', 'upload'}

        for step in steps:
            if step.action_type in high_risk_actions:
                return 'high'
            elif step.action_type in medium_risk_actions:
                return 'medium'

        return 'low'


class ExecutorDecider:
    """
    Decides which executor to use based on the execution plan
    """

    def decide_executor(self, plan: ExecutionPlan) -> str:
        """Decide which executor should handle the plan"""
        if plan.execution_type == ExecutionType.READ_ONLY:
            return "read_executor"
        elif plan.execution_type in [ExecutionType.MODIFY, ExecutionType.MIXED]:
            return "changes_executor"
        else:
            raise ValueError(f"Unknown execution type: {plan.execution_type}")


class ReadExecutor:
    """
    Executes read-only operations without requiring user approval
    """

    def __init__(self, client_manager: MCPClientManager):
        self.client_manager = client_manager

    def execute_plan(self, plan: ExecutionPlan) -> List[ExecutionResult]:
        """Execute a read-only plan"""
        logger.info(f"Executing read-only plan {plan.plan_id}")

        results = []

        for step in plan.steps:
            try:
                start_time = time.time()

                # Get the appropriate MCP client
                client = self.client_manager.get_client(step.mcp_client)
                if not client:
                    raise Exception(f"MCP client '{step.mcp_client}' not found")

                # Execute the tool
                if hasattr(client, 'call_tool_request'):
                    output = client.call_tool_request(step.tool_name, step.parameters)
                else:
                    raise Exception(f"Client {step.mcp_client} doesn't support tool execution")

                execution_time = time.time() - start_time

                result = ExecutionResult(
                    step_number=step.step_number,
                    success=True,
                    output=output,
                    execution_time=execution_time
                )

                results.append(result)
                logger.info(f"Completed step {step.step_number} in {execution_time:.2f}s")

            except Exception as e:
                logger.error(f"Step {step.step_number} failed: {e}")
                results.append(ExecutionResult(
                    step_number=step.step_number,
                    success=False,
                    output=None,
                    error=str(e)
                ))

        return results


class ChangesExecutor:
    """
    Handles operations that make changes, requiring user approval
    """

    def __init__(self, client_manager: MCPClientManager):
        self.client_manager = client_manager
        self.pending_executions: Dict[str, Tuple[ExecutionPlan, str]] = {}

    def prepare_execution(self, plan: ExecutionPlan) -> str:
        """Prepare execution plan and return execution summary for user approval"""
        execution_summary = self._create_execution_summary(plan)

        # Store the plan for later execution
        self.pending_executions[plan.plan_id] = (plan, execution_summary)

        return execution_summary

    def execute_with_approval(self, plan_id: str, user_approved: bool) -> List[ExecutionResult]:
        """Execute plan if user approved"""
        if plan_id not in self.pending_executions:
            raise Exception(f"No pending execution found for plan {plan_id}")

        plan, summary = self.pending_executions[plan_id]

        if not user_approved:
            logger.info(f"User rejected execution of plan {plan_id}")
            del self.pending_executions[plan_id]
            return [ExecutionResult(
                step_number=0,
                success=False,
                output=None,
                error="Execution cancelled by user"
            )]

        logger.info(f"User approved execution of plan {plan_id}")

        # Execute the plan
        results = []

        for step in plan.steps:
            try:
                start_time = time.time()

                # Get the appropriate MCP client
                client = self.client_manager.get_client(step.mcp_client)
                if not client:
                    raise Exception(f"MCP client '{step.mcp_client}' not found")

                # Execute the tool
                if hasattr(client, 'call_tool_request'):
                    output = client.call_tool_request(step.tool_name, step.parameters)
                else:
                    raise Exception(f"Client {step.mcp_client} doesn't support tool execution")

                execution_time = time.time() - start_time

                result = ExecutionResult(
                    step_number=step.step_number,
                    success=True,
                    output=output,
                    execution_time=execution_time
                )

                results.append(result)
                logger.info(f"Completed step {step.step_number} in {execution_time:.2f}s")

            except Exception as e:
                logger.error(f"Step {step.step_number} failed: {e}")
                results.append(ExecutionResult(
                    step_number=step.step_number,
                    success=False,
                    output=None,
                    error=str(e)
                ))

                # Stop execution on failure for modification operations
                break

        # Clean up
        del self.pending_executions[plan_id]

        return results

    def _create_execution_summary(self, plan: ExecutionPlan) -> str:
        """Create a human-readable execution summary"""
        summary_parts = [
            f"Execution Plan Summary for: {plan.user_query}",
            f"Plan ID: {plan.plan_id}",
            f"Risk Level: {plan.risk_level.upper()}",
            f"Estimated Duration: {plan.estimated_duration:.1f} seconds",
            "",
            "Planned Actions:"
        ]

        for step in plan.steps:
            action_desc = f"  {step.step_number}. {step.description}"
            if step.action_type in ['delete', 'update']:
                action_desc += " ⚠️"
            summary_parts.append(action_desc)

        summary_parts.extend([
            "",
            "Do you want to proceed with this execution? (yes/no)"
        ])

        return "\n".join(summary_parts)


class Evaluator:
    """
    Evaluates execution results against the original user query
    """

    def __init__(self, llm_api_key: str):
        self.llm_api_key = llm_api_key

    def evaluate_results(self, user_query: str, execution_results: List[ExecutionResult], plan: ExecutionPlan) -> Tuple[
        bool, str]:
        """
        Evaluate if the execution results satisfy the user query

        Returns:
            Tuple of (success: bool, explanation: str)
        """
        try:
            # Check if all steps succeeded
            failed_steps = [r for r in execution_results if not r.success]
            if failed_steps:
                return False, f"Execution failed at steps: {[r.step_number for r in failed_steps]}"

            # Simple heuristic evaluation
            success, explanation = self._heuristic_evaluation(user_query, execution_results)

            if success:
                return True, explanation
            else:
                return False, explanation

        except Exception as e:
            logger.error(f"Evaluation failed: {e}")
            return False, f"Evaluation error: {str(e)}"

    def _heuristic_evaluation(self, user_query: str, results: List[ExecutionResult]) -> Tuple[bool, str]:
        """Simple heuristic-based evaluation"""
        query_lower = user_query.lower()

        # Check if we got meaningful results
        meaningful_results = [r for r in results if r.success and r.output]

        if not meaningful_results:
            return False, "No meaningful results obtained from execution"

        # Basic keyword matching evaluation
        if any(word in query_lower for word in ['search', 'find', 'list']):
            # For search queries, check if we got results
            has_results = any(
                r.output and (
                        isinstance(r.output, dict) and len(r.output) > 0
                        or isinstance(r.output, list) and len(r.output) > 0
                        or isinstance(r.output, str) and len(r.output) > 10
                ) for r in meaningful_results
            )

            if has_results:
                return True, "Successfully retrieved requested information"
            else:
                return False, "No results found for the search query"

        elif any(word in query_lower for word in ['send', 'create', 'upload', 'add']):
            # For creation/sending queries, check for success confirmation
            has_confirmation = any(
                r.output and (
                        'success' in str(r.output).lower()
                        or 'created' in str(r.output).lower()
                        or 'sent' in str(r.output).lower()
                        or 'uploaded' in str(r.output).lower()
                ) for r in meaningful_results
            )

            if has_confirmation:
                return True, "Successfully completed the requested action"
            else:
                return False, "Action may not have completed successfully"

        # Default to success if we got results
        return True, f"Execution completed with {len(meaningful_results)} successful steps"


class MultiMCPAgent:
    """
    Main agent class that orchestrates the entire execution pipeline
    """

    def __init__(self, llm_api_key: str):
        self.client_manager = MCPClientManager()
        self.planner = Planner(self.client_manager, llm_api_key)
        self.executor_decider = ExecutorDecider()
        self.read_executor = ReadExecutor(self.client_manager)
        self.changes_executor = ChangesExecutor(self.client_manager)
        self.evaluator = Evaluator(llm_api_key)

        self.execution_history: List[Dict] = []
        self.retry_limit = 1

    def register_mcp_client(self, name: str, client: Any):
        """Register an MCP client with the agent"""
        self.client_manager.register_client(name, client)

    def process_query(self, user_query: str) -> Dict[str, Any]:
        """
        Main method to process a user query through the complete pipeline
        """
        logger.info(f"Processing user query: {user_query}")

        execution_log = {
            "query": user_query,
            "timestamp": datetime.now(timezone.utc),
            "stages": []
        }

        try:
            # Stage 1: Planning
            logger.info("Stage 1: Creating execution plan")
            plan = self.planner.create_plan(user_query)
            execution_log["stages"].append({
                "stage": "planning",
                "status": "success",
                "plan_id": plan.plan_id,
                "execution_type": plan.execution_type.value,
                "steps_count": len(plan.steps)
            })

            # Stage 2: Executor Decision
            logger.info("Stage 2: Deciding executor")
            executor_type = self.executor_decider.decide_executor(plan)
            execution_log["stages"].append({
                "stage": "executor_decision",
                "status": "success",
                "executor_type": executor_type
            })

            # Stage 3: Execution
            logger.info(f"Stage 3: Executing with {executor_type}")

            if executor_type == "read_executor":
                # Direct execution for read-only operations
                results = self.read_executor.execute_plan(plan)
                execution_log["stages"].append({
                    "stage": "execution",
                    "status": "completed",
                    "executor": "read",
                    "results_count": len(results)
                })

                # Stage 4: Evaluation
                return self._evaluate_and_respond(user_query, results, plan, execution_log)

            elif executor_type == "changes_executor":
                # Request user approval for modification operations
                execution_summary = self.changes_executor.prepare_execution(plan)
                execution_log["stages"].append({
                    "stage": "execution_preparation",
                    "status": "pending_approval",
                    "executor": "changes"
                })

                return {
                    "status": "pending_approval",
                    "plan_id": plan.plan_id,
                    "execution_summary": execution_summary,
                    "requires_approval": True,
                    "execution_log": execution_log
                }

        except Exception as e:
            logger.error(f"Query processing failed: {e}")
            execution_log["stages"].append({
                "stage": "error",
                "status": "failed",
                "error": str(e)
            })

            return {
                "status": "error",
                "error": str(e),
                "execution_log": execution_log
            }

    def execute_with_approval(self, plan_id: str, user_approved: bool) -> Dict[str, Any]:
        """Execute a plan that required user approval"""
        logger.info(f"Executing plan {plan_id} with approval: {user_approved}")

        try:
            # Get the original plan from changes executor
            if plan_id not in self.changes_executor.pending_executions:
                return {
                    "status": "error",
                    "error": "Plan not found or already executed"
                }

            plan, _ = self.changes_executor.pending_executions[plan_id]

            # Execute with approval
            results = self.changes_executor.execute_with_approval(plan_id, user_approved)

            if not user_approved:
                return {
                    "status": "cancelled",
                    "message": "Execution cancelled by user"
                }

            # Evaluate results
            execution_log = {
                "query": plan.user_query,
                "timestamp": datetime.now(timezone.utc),
                "stages": [
                    {"stage": "execution", "status": "completed", "executor": "changes", "results_count": len(results)}
                ]
            }

            return self._evaluate_and_respond(plan.user_query, results, plan, execution_log)

        except Exception as e:
            logger.error(f"Approved execution failed: {e}")
            return {
                "status": "error",
                "error": str(e)
            }

    def _evaluate_and_respond(self, user_query: str, results: List[ExecutionResult], plan: ExecutionPlan,
                              execution_log: Dict) -> Dict[str, Any]:
        """Evaluate results and create response"""
        retry_count = 0

        while retry_count <= self.retry_limit:
            # Stage 4: Evaluation
            logger.info(f"Stage 4: Evaluating results (attempt {retry_count + 1})")
            success, explanation = self.evaluator.evaluate_results(user_query, results, plan)

            execution_log["stages"].append({
                "stage": "evaluation",
                "status": "success" if success else "retry_needed",
                "explanation": explanation,
                "attempt": retry_count + 1
            })

            if success:
                # Success - create final response
                response_summary = self._create_response_summary(user_query, results, explanation)
                execution_log["final_status"] = "success"

                # Store in history
                self.execution_history.append(execution_log)

                return {
                    "status": "success",
                    "response": response_summary,
                    "results": [{"step": r.step_number, "success": r.success, "output": r.output} for r in results],
                    "execution_log": execution_log
                }

            elif retry_count < self.retry_limit:
                # Retry once
                logger.info("Results didn't meet expectations, retrying with new plan")
                retry_count += 1

                # Create new plan
                new_plan = self.planner.create_plan(user_query)

                # Execute new plan (only read operations for retry)
                if new_plan.execution_type == ExecutionType.READ_ONLY:
                    results = self.read_executor.execute_plan(new_plan)
                else:
                    break  # Don't retry modification operations
            else:
                # Failed after retry
                break

        # Final failure
        execution_log["final_status"] = "failed"
        execution_log["stages"].append({
            "stage": "final_failure",
            "status": "failed",
            "message": "Unable to satisfy query after retry"
        })

        self.execution_history.append(execution_log)

        return {
            "status": "failed",
            "message": "I was unable to complete your request successfully. " + explanation,
            "execution_log": execution_log
        }

    def _create_response_summary(self, user_query: str, results: List[ExecutionResult], explanation: str) -> str:
        """Create a human-readable response summary"""
        successful_results = [r for r in results if r.success]

        summary_parts = [
            f"I've successfully processed your request: \"{user_query}\"",
            "",
            explanation,
            ""
        ]

        if len(successful_results) > 1:
            summary_parts.append(f"Completed {len(successful_results)} operations:")
            for i, result in enumerate(successful_results, 1):
                summary_parts.append(f"  {i}. Step {result.step_number} - Success")

        # Add relevant output snippets
        for result in successful_results:
            if result.output and isinstance(result.output, dict):
                if 'result' in result.output:
                    summary_parts.append(f"\nResults: {result.output['result']}")
                elif 'success' in result.output:
                    summary_parts.append(f"\nOperation completed successfully")

        return "\n".join(summary_parts)

    def get_execution_history(self) -> List[Dict]:
        """Get execution history"""
        return self.execution_history

    def health_check(self) -> Dict[str, Any]:
        """Check health of all system components"""
        return {
            "agent_status": "healthy",
            "registered_clients": self.client_manager.list_clients(),
            "client_health": self.client_manager.health_check_all(),
            "pending_executions": len(self.changes_executor.pending_executions),
            "execution_history_count": len(self.execution_history)
        }


# Example usage and integration with Flask
class AgentFlaskIntegration:
    """
    Flask integration for the Multi-MCP Agent
    """

    def __init__(self, app, groq_api_key: str):
        self.app = app
        self.agent = MultiMCPAgent(groq_api_key)
        self._setup_routes()

    def _setup_routes(self):
        """Setup Flask routes for the agent"""

        @self.app.route('/agent/query', methods=['POST'])
        def process_query():
            try:
                data = request.json
                user_query = data.get('query')

                if not user_query:
                    return jsonify({"error": "Query is required"}), 400

                result = self.agent.process_query(user_query)
                return jsonify(result)

            except Exception as e:
                return jsonify({"error": str(e)}), 500

        @self.app.route('/agent/approve/<plan_id>', methods=['POST'])
        def approve_execution(plan_id):
            try:
                data = request.json
                user_approved = data.get('approved', False)

                result = self.agent.execute_with_approval(plan_id, user_approved)
                return jsonify(result)

            except Exception as e:
                return jsonify({"error": str(e)}), 500

        @self.app.route('/agent/health', methods=['GET'])
        def agent_health():
            return jsonify(self.agent.health_check())

        @self.app.route('/agent/history', methods=['GET'])
        def execution_history():
            return jsonify({
                "history": self.agent.get_execution_history(),
                "count": len(self.agent.get_execution_history())
            })

        @self.app.route('/agent/clients', methods=['GET'])
        def list_clients():
            return jsonify({
                "registered_clients": self.agent.client_manager.list_clients(),
                "client_health": self.agent.client_manager.health_check_all()
            })

    def register_google_workspace_client(self, server_url: str = "http://localhost:8000"):
        """Register Google Workspace MCP client"""
        try:
            client = GoogleWorkspaceMCPClient(server_url=server_url)
            self.agent.register_mcp_client("google_workspace", client)
            logger.info("Google Workspace MCP client registered successfully")
        except Exception as e:
            logger.error(f"Failed to register Google Workspace client: {e}")
            raise


# Example usage function
def create_agent_system(app, groq_api_key: str, google_workspace_server_url: str = "http://localhost:8000"):
    """
    Create and configure the complete agent system

    Args:
        app: Flask application instance
        groq_api_key: Groq API key for LLM operations
        google_workspace_server_url: URL of the Google Workspace MCP server

    Returns:
        AgentFlaskIntegration instance
    """
    try:
        # Create the agent integration
        agent_integration = AgentFlaskIntegration(app, groq_api_key)

        # Register Google Workspace MCP client
        agent_integration.register_google_workspace_client(google_workspace_server_url)

        logger.info("Multi-MCP Agent system created successfully")
        return agent_integration

    except Exception as e:
        logger.error(f"Failed to create agent system: {e}")
        raise


# Advanced features and utilities
class AdvancedPlanningFeatures:
    """
    Advanced features for the planning system
    """

    @staticmethod
    def create_complex_plan(user_query: str, available_tools: Dict) -> List[PlanStep]:
        """
        Create more complex plans with dependencies and conditional logic
        """
        steps = []
        query_lower = user_query.lower()

        # Example: Multi-step email workflow
        if "send summary email" in query_lower and "calendar" in query_lower:
            # Step 1: Get calendar events
            steps.append(PlanStep(
                step_number=1,
                description="Retrieve calendar events for summary",
                action_type="read",
                mcp_client="google_workspace",
                tool_name="calendar_list_events",
                parameters={"time_min": "2024-01-01T00:00:00Z", "time_max": "2024-12-31T23:59:59Z"},
                expected_output="List of calendar events"
            ))

            # Step 2: Compose email with calendar data
            steps.append(PlanStep(
                step_number=2,
                description="Compose summary email with calendar data",
                action_type="write",
                mcp_client="google_workspace",
                tool_name="gmail_send",
                parameters={"subject": "Calendar Summary", "body": "Generated from calendar data"},
                expected_output="Email sent confirmation",
                dependencies=[1]
            ))

        # Example: Document workflow
        elif "create document" in query_lower and "drive" in query_lower:
            # Step 1: Create document
            steps.append(PlanStep(
                step_number=1,
                description="Create new document",
                action_type="write",
                mcp_client="google_workspace",
                tool_name="docs_create",
                parameters={"title": "New Document"},
                expected_output="Document created"
            ))

            # Step 2: Upload to Drive
            steps.append(PlanStep(
                step_number=2,
                description="Share document via Drive",
                action_type="write",
                mcp_client="google_workspace",
                tool_name="drive_share",
                parameters={"file_id": "from_step_1", "emails": ["user@example.com"]},
                expected_output="Document shared",
                dependencies=[1]
            ))

        return steps if steps else AdvancedPlanningFeatures._fallback_plan(user_query)

    @staticmethod
    def _fallback_plan(user_query: str) -> List[PlanStep]:
        """Create a fallback plan for unrecognized queries"""
        return [PlanStep(
            step_number=1,
            description="Search for relevant information",
            action_type="read",
            mcp_client="google_workspace",
            tool_name="search_web",
            parameters={"query": user_query},
            expected_output="Search results"
        )]


class ResultAggregator:
    """
    Aggregates and processes results from multiple execution steps
    """

    def __init__(self):
        self.aggregated_data = {}

    def aggregate_results(self, results: List[ExecutionResult]) -> Dict[str, Any]:
        """
        Aggregate results from multiple execution steps
        """
        aggregated = {
            "total_steps": len(results),
            "successful_steps": len([r for r in results if r.success]),
            "failed_steps": len([r for r in results if not r.success]),
            "total_execution_time": sum(r.execution_time for r in results),
            "results_by_step": {},
            "combined_outputs": [],
            "errors": []
        }

        for result in results:
            aggregated["results_by_step"][f"step_{result.step_number}"] = {
                "success": result.success,
                "output": result.output,
                "execution_time": result.execution_time,
                "error": result.error
            }

            if result.success and result.output:
                aggregated["combined_outputs"].append(result.output)

            if result.error:
                aggregated["errors"].append({
                    "step": result.step_number,
                    "error": result.error
                })

        return aggregated

    def extract_key_information(self, aggregated_results: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract key information from aggregated results
        """
        key_info = {
            "summary": f"Executed {aggregated_results['total_steps']} steps with {aggregated_results['successful_steps']} successes",
            "execution_time": f"{aggregated_results['total_execution_time']:.2f} seconds",
            "success_rate": f"{(aggregated_results['successful_steps'] / aggregated_results['total_steps'] * 100):.1f}%",
            "has_errors": len(aggregated_results['errors']) > 0,
            "key_outputs": []
        }

        # Extract key outputs based on content type
        for output in aggregated_results["combined_outputs"]:
            if isinstance(output, dict):
                if 'result' in output:
                    key_info["key_outputs"].append(output['result'])
                elif 'data' in output:
                    key_info["key_outputs"].append(output['data'])
                elif 'message' in output:
                    key_info["key_outputs"].append(output['message'])
            elif isinstance(output, str):
                key_info["key_outputs"].append(output[:200] + "..." if len(output) > 200 else output)

        return key_info


class EnhancedEvaluator(Evaluator):
    """
    Enhanced evaluator with more sophisticated evaluation logic
    """

    def __init__(self, llm_api_key: str):
        super().__init__(llm_api_key)
        self.result_aggregator = ResultAggregator()

    def evaluate_results(self, user_query: str, execution_results: List[ExecutionResult], plan: ExecutionPlan) -> Tuple[
        bool, str]:
        """
        Enhanced evaluation with aggregation and deeper analysis
        """
        try:
            # Aggregate results first
            aggregated = self.result_aggregator.aggregate_results(execution_results)
            key_info = self.result_aggregator.extract_key_information(aggregated)

            # Check basic success criteria
            if aggregated["failed_steps"] > 0:
                return False, f"Execution failed: {aggregated['failed_steps']} steps failed out of {aggregated['total_steps']}"

            # Enhanced evaluation logic
            success, explanation = self._enhanced_evaluation(user_query, aggregated, key_info, plan)

            return success, explanation

        except Exception as e:
            logger.error(f"Enhanced evaluation failed: {e}")
            return False, f"Evaluation error: {str(e)}"

    def _enhanced_evaluation(self, user_query: str, aggregated: Dict, key_info: Dict, plan: ExecutionPlan) -> Tuple[
        bool, str]:
        """
        Enhanced evaluation logic with context awareness
        """
        query_lower = user_query.lower()

        # Context-aware evaluation based on query intent
        if any(word in query_lower for word in ['search', 'find', 'look', 'get', 'retrieve']):
            return self._evaluate_retrieval_query(user_query, aggregated, key_info)

        elif any(word in query_lower for word in ['send', 'create', 'make', 'add', 'new']):
            return self._evaluate_creation_query(user_query, aggregated, key_info)

        elif any(word in query_lower for word in ['update', 'modify', 'change', 'edit']):
            return self._evaluate_modification_query(user_query, aggregated, key_info)

        elif any(word in query_lower for word in ['delete', 'remove', 'cancel']):
            return self._evaluate_deletion_query(user_query, aggregated, key_info)

        else:
            return self._evaluate_generic_query(user_query, aggregated, key_info)

    def _evaluate_retrieval_query(self, query: str, aggregated: Dict, key_info: Dict) -> Tuple[bool, str]:
        """Evaluate retrieval/search queries"""
        if not key_info["key_outputs"]:
            return False, "No data retrieved for your search query"

        # Check if we got meaningful data
        meaningful_results = [output for output in key_info["key_outputs"] if output and len(str(output)) > 10]

        if meaningful_results:
            return True, f"Successfully retrieved {len(meaningful_results)} relevant results"
        else:
            return False, "Retrieved data appears to be empty or incomplete"

    def _evaluate_creation_query(self, query: str, aggregated: Dict, key_info: Dict) -> Tuple[bool, str]:
        """Evaluate creation/sending queries"""
        success_indicators = ['success', 'created', 'sent', 'added', 'completed']

        for output in key_info["key_outputs"]:
            output_str = str(output).lower()
            if any(indicator in output_str for indicator in success_indicators):
                return True, "Successfully completed the creation/sending operation"

        return False, "Creation/sending operation may not have completed successfully"

    def _evaluate_modification_query(self, query: str, aggregated: Dict, key_info: Dict) -> Tuple[bool, str]:
        """Evaluate modification queries"""
        modification_indicators = ['updated', 'modified', 'changed', 'edited', 'success']

        for output in key_info["key_outputs"]:
            output_str = str(output).lower()
            if any(indicator in output_str for indicator in modification_indicators):
                return True, "Successfully completed the modification operation"

        return False, "Modification operation may not have completed successfully"

    def _evaluate_deletion_query(self, query: str, aggregated: Dict, key_info: Dict) -> Tuple[bool, str]:
        """Evaluate deletion queries"""
        deletion_indicators = ['deleted', 'removed', 'cancelled', 'success']

        for output in key_info["key_outputs"]:
            output_str = str(output).lower()
            if any(indicator in output_str for indicator in deletion_indicators):
                return True, "Successfully completed the deletion operation"

        return False, "Deletion operation may not have completed successfully"

    def _evaluate_generic_query(self, query: str, aggregated: Dict, key_info: Dict) -> Tuple[bool, str]:
        """Evaluate generic queries"""
        if aggregated["successful_steps"] == aggregated["total_steps"] and key_info["key_outputs"]:
            return True, f"Successfully processed your request with {key_info['success_rate']} success rate"
        else:
            return False, f"Query processing incomplete - {aggregated['failed_steps']} steps failed"


# Testing and example usage
def example_usage():
    """
    Example of how to use the Multi-MCP Agent system
    """
    # This would be integrated with your Flask app
    from flask import Flask

    app = Flask(__name__)

    # Initialize the agent system
    groq_api_key = "your-groq-api-key"
    agent_integration = create_agent_system(app, groq_api_key)

    # Example queries that the agent can handle:
    example_queries = [
        "Search my emails for messages about the project meeting",
        "Create a new calendar event for team standup tomorrow at 9 AM",
        "Send an email to john@example.com with project updates",
        "List all files in my Google Drive",
        "Create a new Google Doc titled 'Meeting Notes'",
        "Search the web for information about AI developments"
    ]

    # The agent will:
    # 1. Create execution plans for these queries
    # 2. Determine if user approval is needed
    # 3. Execute the plans using appropriate MCP clients
    # 4. Evaluate results and provide feedback
    # 5. Handle retries if initial execution doesn't meet expectations

    return agent_integration


if __name__ == "__main__":
    # Example of standalone usage
    logging.basicConfig(level=logging.INFO)

    # Create agent
    agent = MultiMCPAgent(GROQ_API_KEY)

    # Register Google Workspace client
    google_client = GoogleWorkspaceMCPClient("http://localhost:8000")
    agent.register_mcp_client("google_workspace", google_client)

    # Process a query
    result = agent.process_query("Search my emails for messages about the project")
    print(json.dumps(result, indent=2, default=str))