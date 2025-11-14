"""
LangGraph agent state machine definition.
"""

from langgraph.graph import StateGraph, END
from app.agents.state import AgentState
from app.agents.nodes import (
    analyze_query_node,
    retrieve_context_node,
    generate_response_node,
    calculate_confidence_node,
    decision_node,
    format_output_node,
    invoke_tools_node,
    route_decision_node,
)
from app.core.logging import get_logger

logger = get_logger(__name__)


def create_agent_graph() -> StateGraph:
    """
    Create the LangGraph agent workflow with tool invocation support.

    Flow:
    1. analyze_query - Classify intent, extract entities, determine routing
    2. route_decision - Conditional routing based on analysis:
       - tool_invocation → invoke_tools → generate_response
       - standard_rag → retrieve_context → generate_response
       - direct_escalation → generate_response (with escalation flag)
    3. invoke_tools (if needed) - Execute tools (calculator, web search, MCP)
    4. retrieve_context (if needed) - Get relevant documents from vector store
    5. generate_response - Create response with LLM (with tool results or context)
    6. calculate_confidence - Score the response quality
    7. decision - Determine if confidence meets threshold
    8. format_output - Prepare final response

    Returns:
        Compiled LangGraph workflow
    """
    # Create graph
    workflow = StateGraph(AgentState)

    # Add nodes
    workflow.add_node("analyze_query", analyze_query_node)
    workflow.add_node("invoke_tools", invoke_tools_node)
    workflow.add_node("retrieve_context", retrieve_context_node)
    workflow.add_node("generate_response", generate_response_node)
    workflow.add_node("calculate_confidence", calculate_confidence_node)
    workflow.add_node("decision", decision_node)
    workflow.add_node("format_output", format_output_node)

    # Define edges (workflow flow)
    workflow.set_entry_point("analyze_query")

    # Conditional routing after query analysis
    workflow.add_conditional_edges(
        "analyze_query",
        route_decision_node,
        {
            "invoke_tools": "invoke_tools",
            "retrieve_context": "retrieve_context",
            "generate_response": "generate_response",
        }
    )

    # Tool invocation path
    workflow.add_edge("invoke_tools", "generate_response")

    # Standard RAG path
    workflow.add_edge("retrieve_context", "generate_response")

    # Common path after response generation
    workflow.add_edge("generate_response", "calculate_confidence")
    workflow.add_edge("calculate_confidence", "decision")
    workflow.add_edge("decision", "format_output")
    workflow.add_edge("format_output", END)

    # Compile graph
    compiled_graph = workflow.compile()

    logger.info("Agent graph compiled successfully with tool invocation and conditional routing")

    return compiled_graph


# Global agent instance
_agent_graph = None


def get_agent_graph() -> StateGraph:
    """
    Get or create the global agent graph instance.

    Returns:
        Compiled agent graph
    """
    global _agent_graph
    if _agent_graph is None:
        _agent_graph = create_agent_graph()
    return _agent_graph
