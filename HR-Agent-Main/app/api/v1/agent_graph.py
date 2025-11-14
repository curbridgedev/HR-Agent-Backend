"""
Agent graph visualization API endpoints.

Provides endpoints to visualize the LangGraph agent workflow.
"""

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response, JSONResponse
from typing import Literal
from app.agents.graph import get_agent_graph
from app.core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter()


@router.get(
    "/graph/mermaid",
    summary="Get agent graph as Mermaid diagram",
    description="Returns the agent workflow graph as a Mermaid diagram string",
    response_model=None,  # Disable response model validation for custom response types
)
async def get_agent_graph_mermaid(
    format: Literal["text", "json"] = Query(
        "text",
        description="Output format: 'text' for raw Mermaid syntax, 'json' for structured response"
    )
):
    """
    Get the agent graph as a Mermaid diagram.

    The graph is generated dynamically from the current agent configuration,
    so any changes to the agent workflow will be reflected automatically.

    Returns:
        - format='text': Raw Mermaid diagram syntax (text/plain)
        - format='json': JSON with mermaid field containing the diagram
    """
    try:
        # Get the compiled agent graph
        agent_graph = get_agent_graph()

        # Generate Mermaid diagram
        mermaid_diagram = agent_graph.get_graph().draw_mermaid()

        logger.info("Generated agent graph Mermaid diagram")

        if format == "json":
            return JSONResponse(
                content={
                    "success": True,
                    "mermaid": mermaid_diagram,
                    "nodes": _extract_node_info(agent_graph),
                }
            )
        else:
            return Response(
                content=mermaid_diagram,
                media_type="text/plain",
                headers={
                    "Content-Disposition": "inline; filename=agent-graph.mmd"
                }
            )

    except Exception as e:
        logger.error(f"Failed to generate Mermaid diagram: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate graph visualization: {str(e)}"
        )


@router.get(
    "/graph/png",
    summary="Get agent graph as PNG image",
    description="Returns the agent workflow graph as a PNG image",
    response_model=None,  # Disable response model validation for custom response types
)
async def get_agent_graph_png():
    """
    Get the agent graph as a PNG image.

    The graph is generated dynamically from the current agent configuration,
    so any changes to the agent workflow will be reflected automatically.

    Uses Mermaid.ink API to render the diagram as PNG.

    Returns:
        PNG image (image/png)
    """
    try:
        # Get the compiled agent graph
        agent_graph = get_agent_graph()

        # Generate PNG image
        # Note: This requires network access to mermaid.ink API
        png_bytes = agent_graph.get_graph().draw_mermaid_png()

        logger.info("Generated agent graph PNG image")

        return Response(
            content=png_bytes,
            media_type="image/png",
            headers={
                "Content-Disposition": "inline; filename=agent-graph.png",
                "Cache-Control": "no-cache"  # Always fetch fresh since graph may change
            }
        )

    except Exception as e:
        logger.error(f"Failed to generate PNG image: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate graph image: {str(e)}"
        )


@router.get(
    "/graph/info",
    summary="Get agent graph metadata",
    description="Returns metadata about the agent graph structure",
)
async def get_agent_graph_info():
    """
    Get metadata about the agent graph structure.

    Returns information about nodes, edges, and configuration
    without generating the full visualization.

    Returns:
        JSON with graph metadata
    """
    try:
        # Get the compiled agent graph
        agent_graph = get_agent_graph()
        graph_obj = agent_graph.get_graph()

        # Extract graph information
        nodes = _extract_node_info(agent_graph)
        edges = _extract_edge_info(graph_obj)

        logger.info("Retrieved agent graph metadata")

        return {
            "success": True,
            "nodes": nodes,
            "edges": edges,
            "entry_point": "analyze_query",
            "total_nodes": len(nodes),
            "total_edges": len(edges),
        }

    except Exception as e:
        logger.error(f"Failed to get graph info: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get graph metadata: {str(e)}"
        )


def _extract_node_info(agent_graph) -> list[dict]:
    """
    Extract information about nodes in the graph.

    Args:
        agent_graph: Compiled LangGraph agent

    Returns:
        List of node information dictionaries
    """
    try:
        graph_obj = agent_graph.get_graph()
        nodes = []

        # Get node names from the graph
        for node in graph_obj.nodes:
            node_info = {
                "id": node.id,
                "name": node.id,
                "type": _classify_node_type(node.id),
            }
            nodes.append(node_info)

        return nodes

    except Exception as e:
        logger.warning(f"Failed to extract node info: {e}")
        return []


def _classify_node_type(node_name: str) -> str:
    """
    Classify node type based on its name.

    Args:
        node_name: Name of the node

    Returns:
        Node type classification
    """
    if node_name == "__start__":
        return "start"
    elif node_name == "__end__":
        return "end"
    elif "analyze" in node_name.lower():
        return "analysis"
    elif "retrieve" in node_name.lower():
        return "retrieval"
    elif "generate" in node_name.lower():
        return "generation"
    elif "confidence" in node_name.lower():
        return "scoring"
    elif "decision" in node_name.lower():
        return "decision"
    elif "tool" in node_name.lower():
        return "tool"
    elif "format" in node_name.lower():
        return "formatting"
    else:
        return "processing"


def _extract_edge_info(graph_obj) -> list[dict]:
    """
    Extract information about edges in the graph.

    Args:
        graph_obj: LangGraph graph object

    Returns:
        List of edge information dictionaries
    """
    try:
        edges = []

        for edge in graph_obj.edges:
            edge_info = {
                "source": edge.source,
                "target": edge.target,
                "conditional": hasattr(edge, 'data') and edge.data is not None,
            }
            edges.append(edge_info)

        return edges

    except Exception as e:
        logger.warning(f"Failed to extract edge info: {e}")
        return []
