"""
LangGraph agent nodes - individual processing steps.
"""

import asyncio
import json
import re
import time
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.mcp_integration import get_mcp_client_manager
from app.agents.state import AgentState
from app.agents.tools import get_tool_registry
from app.core.config import settings
from app.core.logging import get_logger
from app.db.supabase import get_supabase_client
from app.db.vector import hybrid_search
from app.models.query_analysis import (
    COMPAYTENCE_PRODUCTS,
    PAYMENT_CONCEPTS,
    PAYMENT_METHODS,
    TECHNICAL_TERMS,
    EntityType,
    ExtractedEntity,
    QueryAnalysisResult,
    QueryComplexity,
    QueryIntent,
    RoutingDecision,
)
from app.services.agent_config import get_active_config
from app.services.embedding import generate_embedding
from app.services.prompts import get_active_prompt, get_formatted_prompt
from app.utils.llm_client import get_chat_model

logger = get_logger(__name__)


async def analyze_query_node(state: AgentState) -> dict[str, Any]:
    """
    Node: Analyze user query for intent, complexity, and entities.

    Uses LLM with structured output to classify queries and extract key information.
    This analysis guides subsequent processing decisions.

    Args:
        state: Current agent state

    Returns:
        Updated state with query_analysis field populated
    """
    try:
        start_time = time.time()
        query = state["query"]

        logger.info(f"Analyzing query: {query[:100]}...")

        # Load agent configuration for model settings
        agent_config = await get_active_config()
        if agent_config:
            model_settings = agent_config.config.model_settings
            provider = model_settings.provider
            model = model_settings.model
            logger.debug(f"Using model from config: provider={provider}, model={model}")
        else:
            # Fallback to gpt-4-turbo for better JSON support
            provider = "openai"
            model = "gpt-4-turbo"
            logger.warning(f"Using fallback model: provider={provider}, model={model}")

        # Prepare variables for prompt template
        prompt_variables = {
            "query": query,
            "products": ', '.join(COMPAYTENCE_PRODUCTS),
            "payment_methods": ', '.join(PAYMENT_METHODS[:10]),
            "concepts": ', '.join(PAYMENT_CONCEPTS[:10]),
            "technical_terms": ', '.join(TECHNICAL_TERMS[:10]),
        }

        # Load analysis user prompt from database
        analysis_prompt, user_version = await get_formatted_prompt(
            name="query_analysis_user",
            prompt_type="analysis",
            variables=prompt_variables,
            fallback=f"""Analyze the following user query for a finance/payment AI assistant.

Query: "{query}"

Provide a comprehensive analysis including:

1. INTENT CLASSIFICATION:
   - factual: Simple fact retrieval
   - procedural: How-to, step-by-step instructions
   - troubleshooting: Problem-solving, debugging
   - comparison: Comparing options or features
   - definition: Defining terms or concepts
   - conceptual: Explaining abstract concepts
   - navigational: Finding specific resources
   - transactional: Action-oriented requests
   - unknown: Unable to classify

2. COMPLEXITY ASSESSMENT:
   - simple: Single fact, direct answer
   - moderate: Synthesis of 2-5 facts
   - complex: Multi-step reasoning, 5+ facts
   - very_complex: Deep analysis, extensive reasoning

3. ENTITY EXTRACTION:
   Extract entities and classify them:
   - product: Compaytence features/products
   - payment_method: Payment types (credit card, ACH, wire transfer, etc.)
   - technology: Technical terms (API, SDK, webhook, etc.)
   - concept: Abstract concepts (compliance, security, fraud detection, etc.)
   - company: Organization names
   - amount: Monetary amounts
   - date: Time references
   - currency: Currency types
   - country: Geographic references
   - feature: Specific features or capabilities

4. ROUTING DECISION:
   - standard_rag: Normal retrieval + generation
   - tool_invocation: Requires external tools (calculator, web search)
   - multi_step_reasoning: Complex reasoning chain
   - direct_escalation: Out of scope, escalate immediately
   - cached_response: Check semantic cache first

5. CONTEXT REQUIREMENTS:
   - Does it need recent/updated information?
   - Does it need multiple document sources?
   - How many documents should be retrieved? (1-20)
   - What similarity threshold? (0.6-0.9)

6. TOOL REQUIREMENTS:
   - Does it require external tools?
   - Which tools might be useful?

7. KEY CONCEPTS AND TOPICS:
   - What are the main concepts?
   - What are the primary topics?

Respond in valid JSON format with this structure:
{{
  "intent": "intent_value",
  "intent_confidence": 0.0-1.0,
  "complexity": "complexity_value",
  "complexity_score": 0.0-1.0,
  "entities": [
    {{"text": "entity_text", "type": "entity_type", "confidence": 0.0-1.0, "metadata": {{}}}}
  ],
  "routing": "routing_decision",
  "routing_confidence": 0.0-1.0,
  "requires_recent_context": true/false,
  "requires_multiple_sources": true/false,
  "suggested_doc_count": 1-20,
  "suggested_similarity_threshold": 0.4-0.6,  // Lower range for better recall
  "requires_tools": true/false,
  "suggested_tools": ["tool1", "tool2"],
  "key_concepts": ["concept1", "concept2"],
  "query_topics": ["topic1", "topic2"],
  "analysis_reasoning": "Explanation of analysis decisions"
}}

Domain Knowledge for Context:
- Products: {', '.join(COMPAYTENCE_PRODUCTS)}
- Payment Methods: {', '.join(PAYMENT_METHODS[:10])}
- Key Concepts: {', '.join(PAYMENT_CONCEPTS[:10])}
- Technical Terms: {', '.join(TECHNICAL_TERMS[:10])}"""
        )

        # Load system prompt from database
        system_prompt, sys_version = await get_formatted_prompt(
            name="query_analysis_system",
            prompt_type="query_analysis_system",
            variables={},
            fallback="You are an expert query analyzer for a finance/payment AI system. Analyze queries precisely and return ONLY valid JSON - no other text, no markdown formatting, just raw JSON."
        )

        logger.info(
            f"Using query analysis prompts: "
            f"system=v{sys_version if sys_version else 'fallback'}, "
            f"user=v{user_version if user_version else 'fallback'}"
        )

        # Get LangChain chat model
        chat_model = get_chat_model(
            provider=provider,
            model=model,
            temperature=0.3,  # Lower temperature for more consistent analysis
            max_tokens=1000,
        )

        # Call LLM for analysis using LangChain
        logger.debug(f"Calling LLM: provider={provider}, model={model}")
        response = await chat_model.ainvoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=analysis_prompt),
        ])

        # Parse JSON response (handle potential markdown formatting)
        response_text = response.content
        # Strip potential markdown code blocks
        if response_text.startswith("```json"):
            response_text = response_text.replace("```json", "").replace("```", "").strip()
        elif response_text.startswith("```"):
            response_text = response_text.replace("```", "").strip()

        analysis_json = json.loads(response_text)

        # Convert entities to ExtractedEntity objects
        # Handle both formats: list of objects OR dict of lists
        entities = []
        entities_data = analysis_json.get("entities", [])

        if isinstance(entities_data, dict):
            # New format: {"products": [], "payment_methods": [], ...}
            for entity_type, entity_list in entities_data.items():
                for entity_text in entity_list:
                    if isinstance(entity_text, str):
                        entities.append(
                            ExtractedEntity(
                                text=entity_text,
                                type=EntityType.PRODUCT if "product" in entity_type else EntityType.CONCEPT,
                                confidence=0.8,
                                metadata={"category": entity_type},
                            )
                        )
        elif isinstance(entities_data, list):
            # Handle list format - could be list of dicts OR list of strings
            for e in entities_data:
                if isinstance(e, dict):
                    # Old format: [{"text": "...", "type": "...", "confidence": ...}]
                    entities.append(
                        ExtractedEntity(
                            text=e["text"],
                            type=EntityType(e["type"]),
                            confidence=e["confidence"],
                            metadata=e.get("metadata", {}),
                        )
                    )
                elif isinstance(e, str):
                    # Simple string list: ["entity1", "entity2"]
                    entities.append(
                        ExtractedEntity(
                            text=e,
                            type=EntityType.CONCEPT,  # Default type
                            confidence=0.7,  # Default confidence
                            metadata={},
                        )
                    )

        # Calculate analysis time
        analysis_time_ms = (time.time() - start_time) * 1000

        # Map prompt values to enum values
        routing_value = analysis_json.get("routing_decision", "retrieval")
        routing_map = {
            "retrieval": "standard_rag",
            "tools": "tool_invocation",
            "direct": "cached_response"
        }

        # Create QueryAnalysisResult
        query_analysis = QueryAnalysisResult(
            original_query=query,
            intent=QueryIntent(analysis_json["intent"]),
            intent_confidence=analysis_json.get("intent_confidence", 0.8),
            complexity=QueryComplexity(analysis_json["complexity"]),
            complexity_score=analysis_json.get("complexity_score", 0.5),
            entities=entities,
            routing=RoutingDecision(routing_map.get(routing_value, "standard_rag")),
            routing_confidence=analysis_json.get("routing_confidence", 0.8),
            requires_recent_context=analysis_json.get("requires_recent_context", False),
            requires_multiple_sources=analysis_json.get(
                "requires_multiple_sources", False
            ),
            suggested_doc_count=analysis_json.get("suggested_doc_count", 5),
            suggested_similarity_threshold=analysis_json.get(
                "suggested_similarity_threshold", 0.45  # Lower default for better recall
            ),
            requires_tools=analysis_json.get("requires_tools", False),
            suggested_tools=analysis_json.get("suggested_tools", []),
            key_concepts=analysis_json.get("key_concepts", []),
            query_topics=analysis_json.get("query_topics", []),
            analysis_reasoning=analysis_json.get("analysis_reasoning", ""),
            analysis_time_ms=analysis_time_ms,
        )

        logger.info(
            f"Query analysis complete: intent={query_analysis.intent}, "
            f"complexity={query_analysis.complexity}, "
            f"routing={query_analysis.routing}, "
            f"entities={len(query_analysis.entities)}, "
            f"time={analysis_time_ms:.0f}ms"
        )

        # Log key insights
        if query_analysis.entities:
            entity_summary = ", ".join(
                [f"{e.text}({e.type})" for e in query_analysis.entities[:3]]
            )
            logger.debug(f"Key entities: {entity_summary}")

        if query_analysis.key_concepts:
            logger.debug(f"Key concepts: {', '.join(query_analysis.key_concepts[:5])}")

        return {"query_analysis": query_analysis}

    except Exception as e:
        logger.error(f"Query analysis failed: {e}", exc_info=True)

        # Fallback analysis on error
        fallback_analysis = QueryAnalysisResult(
            original_query=state["query"],
            intent=QueryIntent.UNKNOWN,
            intent_confidence=0.0,
            complexity=QueryComplexity.MODERATE,
            complexity_score=0.5,
            entities=[],
            routing=RoutingDecision.STANDARD_RAG,
            routing_confidence=0.5,
            requires_recent_context=False,
            requires_multiple_sources=True,
            suggested_doc_count=5,
            suggested_similarity_threshold=0.7,
            requires_tools=False,
            suggested_tools=[],
            key_concepts=[],
            query_topics=[],
            analysis_reasoning=f"Fallback analysis due to error: {str(e)}",
            analysis_time_ms=0.0,
        )

        logger.warning("Using fallback query analysis due to error")

        return {
            "query_analysis": fallback_analysis,
            "error": f"Query analysis error (using fallback): {str(e)}",
        }


async def retrieve_context_node(state: AgentState) -> dict[str, Any]:
    """
    Node: Retrieve relevant context from vector store.

    Performs hybrid search (vector + keyword) to find relevant documents.
    Uses search settings from database configuration.

    Args:
        state: Current agent state

    Returns:
        Updated state with context_documents and context_text
    """
    try:
        logger.info(f"Retrieving context for query: {state['query'][:50]}...")

        # Load agent configuration for search settings
        agent_config = await get_active_config()
        if agent_config:
            search_settings = agent_config.config.search_settings
            logger.debug(
                f"Using database search config: threshold={search_settings.similarity_threshold}, "
                f"max_results={search_settings.max_results}"
            )
        else:
            # Fallback to settings
            from app.models.agent_config import SearchSettings
            search_settings = SearchSettings(
                similarity_threshold=settings.vector_similarity_threshold,
                max_results=settings.vector_max_results,
                use_hybrid_search=True,
            )
            logger.warning("Using fallback search settings (config not available)")

        # Apply query analysis suggestions if available
        query_analysis = state.get("query_analysis")
        if query_analysis:
            # Use query-specific suggestions for doc count and threshold
            suggested_count = query_analysis.suggested_doc_count
            suggested_threshold = query_analysis.suggested_similarity_threshold

            # Use the LOWER threshold to be more inclusive
            # Cap suggested threshold at 0.5 to prevent overly strict filtering
            # This ensures keyword matches can still be found even with lower vector similarity
            capped_suggested = min(suggested_threshold, 0.5)
            final_threshold = min(capped_suggested, search_settings.similarity_threshold)

            logger.debug(
                f"Applying query analysis suggestions: "
                f"count={suggested_count} (was {search_settings.max_results}), "
                f"threshold={final_threshold:.2f} (suggested: {suggested_threshold:.2f}, config: {search_settings.similarity_threshold:.2f})"
            )

            # Use suggested doc count
            final_max_results = suggested_count
        else:
            # Use config defaults
            final_max_results = search_settings.max_results
            final_threshold = search_settings.similarity_threshold

        # Generate embedding for query
        query_embedding = await generate_embedding(state["query"])

        # Perform hybrid search with province filter
        db = get_supabase_client()
        province = state.get("province")  # Get province from state
        
        if not province:
            logger.warning(f"⚠️ No province in state for query: {state['query'][:50]}...")
            logger.warning(f"   State keys: {list(state.keys())}")
        
        logger.info(f"🔍 Retrieving context with province filter: {province or 'NONE'}")
        
        documents = await hybrid_search(
            db=db,
            query_embedding=query_embedding,
            query_text=state["query"],
            match_threshold=final_threshold,
            match_count=final_max_results,
            province=province,  # Filter by province
        )
        
        if province:
            logger.info(f"✅ Province filter '{province}' applied: {len(documents)} results")
            # Check if any documents have wrong province
            for doc in documents[:3]:  # Check first 3
                doc_title = doc.get("document_title") or doc.get("title", "unknown")
                logger.debug(f"   Document: {doc_title[:50]}...")
        else:
            logger.warning(f"⚠️ No province filter - returned {len(documents)} results from all provinces")

        # Format context text
        context_text = ""
        if documents:
            context_text = "\n\n".join(
                [
                    f"Source: {doc.get('source', 'unknown')}\n{doc.get('content', '')}"
                    for doc in documents
                ]
            )

        logger.info(f"Retrieved {len(documents)} context documents")

        return {
            "context_documents": documents,
            "context_text": context_text,
        }

    except Exception as e:
        logger.error(f"Context retrieval failed: {e}", exc_info=True)
        return {
            "context_documents": [],
            "context_text": "",
            "error": f"Context retrieval error: {str(e)}",
        }


async def generate_response_node(state: AgentState) -> dict[str, Any]:
    """
    Node: Generate response using LLM with retrieved context.

    Uses OpenAI GPT-4 to generate a response based on the query and context.
    Loads prompts from database for dynamic prompt management.

    Args:
        state: Current agent state

    Returns:
        Updated state with response and reasoning
    """
    try:
        logger.info("Generating response with LLM")

        # Load agent configuration
        agent_config = await get_active_config()
        if agent_config:
            model_settings = agent_config.config.model_settings
            provider = model_settings.provider
            model = model_settings.model
            logger.debug(
                f"Using database config: v{agent_config.version} "
                f"(provider: {provider}, model: {model}, temp: {model_settings.temperature})"
            )
        else:
            # Fallback to settings
            from app.models.agent_config import ModelSettings
            model_settings = ModelSettings(
                provider="openai",
                model=settings.openai_model,
                temperature=settings.openai_temperature,
                max_tokens=settings.openai_max_tokens,
            )
            provider = "openai"
            model = settings.openai_model
            logger.warning("Using fallback model settings (config not available)")

        # Load system prompt from database
        system_prompt_obj = await get_active_prompt(
            name="main_system_prompt",
            prompt_type="system",
        )

        if system_prompt_obj:
            system_prompt = system_prompt_obj.content
            # Add province context if available
            province = state.get("province")
            if province:
                province_names = {
                    "MB": "Manitoba",
                    "ON": "Ontario", 
                    "SK": "Saskatchewan",
                    "AB": "Alberta",
                    "BC": "British Columbia"
                }
                province_name = province_names.get(province, province)
                province_context = f"\n\nIMPORTANT: You are answering questions about {province_name} ({province}) employment standards. Only reference laws and regulations that apply to {province_name}. Do not mix information from other provinces."
                system_prompt = system_prompt + province_context
            logger.debug(
                f"Using database system prompt: v{system_prompt_obj.version}, province={province}"
            )
        else:
            # Fallback to hardcoded prompt if database fails
            # Include province context if available
            province = state.get("province", "Canada")
            province_context = ""
            if province:
                province_names = {
                    "MB": "Manitoba",
                    "ON": "Ontario", 
                    "SK": "Saskatchewan",
                    "AB": "Alberta",
                    "BC": "British Columbia"
                }
                province_name = province_names.get(province, province)
                province_context = f"\n\nIMPORTANT: You are answering questions about {province_name} ({province}) employment standards. Only reference laws and regulations that apply to {province_name}. Do not mix information from other provinces."
            
            system_prompt = f"""You are a Canadian Employment Standards HR Assistant specializing in provincial employment law.
Your role is to answer questions accurately based on the provided context from official employment standards documents.

{province_context}

If the context contains relevant information, use it to provide a detailed answer with specific references.
If the context is insufficient, clearly state what information is missing.

Always be professional, accurate, and cite specific sections or sources when possible.
Never provide legal advice - only informational guidance based on the documents provided."""
            logger.warning("Using fallback system prompt (database not available)")

        # Format conversation history for context
        conversation_context = ""
        conversation_history = state.get('conversation_history', [])
        if conversation_history:
            conversation_lines = []
            for msg in conversation_history:
                role_label = "User" if msg["role"] == "user" else "Assistant"
                conversation_lines.append(f"{role_label}: {msg['content']}")
            conversation_context = "\n".join(conversation_lines)
            logger.debug(f"Including {len(conversation_history)} previous messages in context")

        # Load retrieval context prompt from database
        retrieval_prompt_obj = await get_active_prompt(
            name="retrieval_context_prompt",
            prompt_type="retrieval",
        )

        if retrieval_prompt_obj:
            # Format the prompt template with actual values
            context_text = state['context_text'] if state['context_text'] else 'No relevant context found.'

            user_prompt = retrieval_prompt_obj.content.format(
                context=context_text,
                query=state['query'],
                conversation_history=conversation_context if conversation_context else 'No previous conversation.'
            )
            logger.debug(
                f"Using database retrieval prompt: v{retrieval_prompt_obj.version}"
            )
        else:
            # Fallback to hardcoded prompt if database fails
            context_section = state['context_text'] if state['context_text'] else 'No relevant context found.'

            # Include conversation history in fallback
            if conversation_context:
                user_prompt = f"""Previous conversation:
{conversation_context}

Knowledge base context:
{context_section}

Current user question: {state['query']}

Please provide a comprehensive answer based on the conversation history and context above."""
            else:
                user_prompt = f"""Context information:
{context_section}

User question: {state['query']}

Please provide a comprehensive answer based on the context above."""
            logger.warning("Using fallback retrieval prompt (database not available)")

        # Get LangChain chat model
        chat_model = get_chat_model(
            provider=provider,
            model=model,
            temperature=model_settings.temperature,
            max_tokens=model_settings.max_tokens,
            top_p=model_settings.top_p,
            frequency_penalty=model_settings.frequency_penalty,
            presence_penalty=model_settings.presence_penalty,
        )

        # Call LLM using LangChain
        logger.debug(f"Calling LLM: provider={provider}, model={model}")
        response = await chat_model.ainvoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ])

        generated_text = response.content
        # Note: Token usage may not be available with all providers
        # LangChain response_metadata may contain usage info for some providers
        tokens_used = 0
        if hasattr(response, 'response_metadata') and 'token_usage' in response.response_metadata:
            token_usage = response.response_metadata['token_usage']
            tokens_used = token_usage.get('total_tokens', 0)
        elif hasattr(response, 'usage_metadata'):
            # Some providers use usage_metadata
            tokens_used = getattr(response.usage_metadata, 'total_tokens', 0)

        logger.info(f"Response generated: {len(generated_text)} chars, {tokens_used} tokens")

        # Track prompt usage if we used database prompts
        if system_prompt_obj:
            try:
                from app.services.prompts import increment_prompt_usage
                await increment_prompt_usage(
                    prompt_id=system_prompt_obj.id,
                    confidence_score=None,  # Will be calculated later
                    escalated=False,  # Will be determined later
                )
            except Exception as e:
                logger.warning(f"Failed to track prompt usage: {e}")

        # Preserve context_documents for confidence calculation
        return {
            "response": generated_text,
            "tokens_used": tokens_used,
            "reasoning": "Generated response based on retrieved context",
            # Preserve context_documents from previous node
            "context_documents": state.get("context_documents", []),
        }

    except Exception as e:
        logger.error(f"Response generation failed: {e}", exc_info=True)
        return {
            "response": "I apologize, but I encountered an error generating a response.",
            "error": f"Response generation error: {str(e)}",
        }


async def _calculate_formula_confidence(
    state: AgentState,
    config: dict[str, Any] | None = None
) -> dict[str, Any]:
    """
    Calculate confidence using algorithmic formula based on retrieval metrics.

    Formula-based confidence calculation (fast, no cost):
    - Similarity score: Weighted average of top 3 results
    - Source quality boost: Count of high-quality sources (similarity > 0.75)
    - Response length boost: Completeness indicator

    Args:
        state: Current agent state
        config: Confidence calculation config (formula_weights)

    Returns:
        Dict with confidence_score, confidence_method, confidence_breakdown
    """
    try:
        context_docs = state.get("context_documents", [])
        response_length = len(state.get("response", ""))

        # Get weights from config or use defaults
        if config and "formula_weights" in config:
            weights = config["formula_weights"]
            similarity_weight = weights.get("similarity", 0.80)
            source_quality_weight = weights.get("source_quality", 0.10)
            response_length_weight = weights.get("response_length", 0.10)
        else:
            similarity_weight = 0.80
            source_quality_weight = 0.10
            response_length_weight = 0.10

        # No documents = zero confidence
        if not context_docs:
            logger.warning("No context documents - formula confidence=0.0")
            return {
                "confidence_score": 0.0,
                "confidence_method": "formula",
                "confidence_breakdown": {
                    "reason": "no_context_documents",
                    "similarity_score": 0.0,
                    "source_boost": 0.0,
                    "length_boost": 0.0,
                }
            }

        # SIMILARITY SCORE: Weighted average of top 3 results
        similarities = [doc.get("similarity", 0) for doc in context_docs[:3]]

        if len(similarities) >= 3:
            # Weighted: 60% best, 30% second, 10% third
            similarity_score = (
                similarities[0] * 0.6 +
                similarities[1] * 0.3 +
                similarities[2] * 0.1
            )
        elif len(similarities) == 2:
            # Weighted: 70% best, 30% second
            similarity_score = similarities[0] * 0.7 + similarities[1] * 0.3
        else:
            # Single document
            similarity_score = similarities[0]

        # SOURCE QUALITY BOOST: Count of high-quality sources
        high_quality_sources = [
            doc for doc in context_docs if doc.get("similarity", 0) > 0.75
        ]

        if len(high_quality_sources) >= 3:
            source_boost = 1.0
        elif len(high_quality_sources) == 2:
            source_boost = 0.6
        elif len(high_quality_sources) == 1:
            source_boost = 0.3
        else:
            source_boost = 0.0

        # RESPONSE LENGTH BOOST: Completeness indicator
        if response_length >= 200:
            length_boost = 1.0
        elif response_length >= 100:
            length_boost = 0.5
        else:
            length_boost = 0.0

        # FINAL CONFIDENCE CALCULATION
        confidence = (
            similarity_score * similarity_weight +
            source_boost * source_quality_weight +
            length_boost * response_length_weight
        )

        # Cap at 1.0
        confidence = min(confidence, 1.0)

        logger.info(
            f"Formula confidence: {confidence:.3f} "
            f"(similarity={similarity_score:.3f}@{similarity_weight*100:.0f}%, "
            f"sources={source_boost:.1f}@{source_quality_weight*100:.0f}%, "
            f"length={length_boost:.1f}@{response_length_weight*100:.0f}%)"
        )

        return {
            "confidence_score": confidence,
            "confidence_method": "formula",
            "confidence_breakdown": {
                "similarity_score": float(similarity_score),
                "source_boost": float(source_boost),
                "length_boost": float(length_boost),
                "high_quality_source_count": len(high_quality_sources),
                "response_length": response_length,
                "weights": {
                    "similarity": similarity_weight,
                    "source_quality": source_quality_weight,
                    "response_length": response_length_weight,
                }
            }
        }

    except Exception as e:
        logger.error(f"Formula confidence calculation failed: {e}", exc_info=True)
        return {
            "confidence_score": 0.0,
            "confidence_method": "formula",
            "confidence_breakdown": {"error": str(e)}
        }


async def _calculate_llm_confidence(
    state: AgentState,
    config: dict[str, Any]
) -> dict[str, Any]:
    """
    Calculate confidence using LLM-based semantic evaluation.

    LLM evaluates:
    - Query understanding
    - Context relevance
    - Response quality
    - Knowledge gaps

    Args:
        state: Current agent state
        config: Confidence calculation config (llm_settings)

    Returns:
        Dict with confidence_score, confidence_method, confidence_breakdown
    """
    try:
        query = state.get("query", "")
        response = state.get("response", "")
        context_docs = state.get("context_documents", [])

        # Extract LLM settings from config
        llm_settings = config.get("llm_settings", {})
        provider = llm_settings.get("provider", "openai")
        model = llm_settings.get("model", "gpt-4o-mini")
        temperature = llm_settings.get("temperature", 0.1)
        max_tokens = llm_settings.get("max_tokens", 100)
        timeout_ms = llm_settings.get("timeout_ms", 5000)

        # Build context text (first 1000 chars)
        context_text = ""
        if context_docs:
            context_chunks = [
                doc.get("content", "") for doc in context_docs[:3]
            ]
            context_text = "\n\n".join(context_chunks)[:1000]

        # Load confidence evaluation prompt from database
        prompt_content, prompt_version_id = await get_formatted_prompt(
            name="confidence_evaluation_prompt",
            prompt_type="confidence",
            variables={
                "query": query[:500],  # Limit query length
                "context": context_text,
                "response": response[:500],  # Limit response length
            },
            fallback=(
                "Evaluate the confidence in the response. "
                "Provide a score between 0.0 and 1.0. "
                "Respond with ONLY a number (e.g., '0.85')."
            )
        )

        logger.debug(
            f"Using LLM for confidence evaluation: {provider}/{model} "
            f"(prompt version: {prompt_version_id})"
        )

        # Initialize LLM with provider support
        llm = get_chat_model(
            provider=provider,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        # Call LLM with timeout
        try:
            llm_response = await asyncio.wait_for(
                llm.ainvoke([
                    SystemMessage(content="You are a confidence evaluator. Respond with ONLY a number between 0.0 and 1.0."),
                    HumanMessage(content=prompt_content)
                ]),
                timeout=timeout_ms / 1000.0
            )

            # Extract confidence score from response
            content = llm_response.content.strip()

            # Try to parse as JSON first (if prompt returns JSON), then as float
            confidence = None
            try:
                # Try JSON parsing first
                if content.startswith('{'):
                    confidence_json = json.loads(content)
                    confidence = float(confidence_json.get("confidence_score", 0.0))
                else:
                    # Try direct float parsing
                    confidence = float(content)

                confidence = max(0.0, min(1.0, confidence))  # Clamp to [0, 1]

                logger.info(
                    f"LLM confidence: {confidence:.3f} "
                    f"({provider}/{model}, raw='{content[:50]}')"
                )

                return {
                    "confidence_score": confidence,
                    "confidence_method": "llm",
                    "confidence_breakdown": {
                        "llm_provider": provider,
                        "llm_model": model,
                        "llm_raw_response": content,
                        "prompt_version_id": prompt_version_id,
                    }
                }
            except (ValueError, json.JSONDecodeError, KeyError) as e:
                logger.warning(f"Failed to parse LLM confidence score: '{content[:100]}', error: {e}")
                # Fallback to formula
                logger.info("Falling back to formula confidence due to parse error")
                return await _calculate_formula_confidence(state, config)

        except TimeoutError:
            logger.warning(
                f"LLM confidence evaluation timed out after {timeout_ms}ms, "
                f"falling back to formula"
            )
            return await _calculate_formula_confidence(state, config)

    except Exception as e:
        logger.error(f"LLM confidence calculation failed: {e}", exc_info=True)
        # Fallback to formula on any error
        logger.info("Falling back to formula confidence due to error")
        return await _calculate_formula_confidence(state, config)


async def _calculate_hybrid_confidence(
    state: AgentState,
    config: dict[str, Any]
) -> dict[str, Any]:
    """
    Calculate confidence using hybrid approach (formula + LLM).

    Strategy:
    1. Calculate formula confidence (retrieval quality metrics)
    2. Calculate LLM confidence (semantic quality evaluation)
    3. Combine both scores with configurable weights

    Args:
        state: Current agent state
        config: Confidence calculation config (hybrid_settings + llm_settings + formula_weights)

    Returns:
        Dict with confidence_score, confidence_method, confidence_breakdown
    """
    try:
        # Extract hybrid weights
        hybrid_settings = config.get("hybrid_settings", {})
        formula_weight = hybrid_settings.get("formula_weight", 0.60)
        llm_weight = hybrid_settings.get("llm_weight", 0.40)

        logger.info(
            f"Calculating hybrid confidence "
            f"(formula={formula_weight*100:.0f}%, llm={llm_weight*100:.0f}%)"
        )

        # Step 1: Calculate formula confidence
        formula_result = await _calculate_formula_confidence(state, config)
        formula_score = formula_result["confidence_score"]

        # Step 2: Calculate LLM confidence
        llm_result = await _calculate_llm_confidence(state, config)
        llm_score = llm_result["confidence_score"]

        # If LLM fell back to formula, just use formula
        if llm_result["confidence_method"] == "formula":
            logger.warning(
                "LLM confidence unavailable, using formula-only for hybrid"
            )
            return {
                "confidence_score": formula_score,
                "confidence_method": "hybrid_fallback_formula",
                "confidence_breakdown": {
                    **formula_result["confidence_breakdown"],
                    "hybrid_note": "LLM unavailable, used formula-only",
                }
            }

        # Step 3: Combine scores with weights
        final_score = (formula_score * formula_weight) + (llm_score * llm_weight)

        logger.info(
            f"Hybrid confidence: {final_score:.3f} "
            f"(formula={formula_score:.3f}@{formula_weight*100:.0f}%, "
            f"llm={llm_score:.3f}@{llm_weight*100:.0f}%)"
        )

        return {
            "confidence_score": final_score,
            "confidence_method": "hybrid",
            "confidence_breakdown": {
                "formula_score": float(formula_score),
                "llm_score": float(llm_score),
                "formula_weight": formula_weight,
                "llm_weight": llm_weight,
                "formula_details": formula_result["confidence_breakdown"],
                "llm_details": llm_result["confidence_breakdown"],
            }
        }

    except Exception as e:
        logger.error(f"Hybrid confidence calculation failed: {e}", exc_info=True)
        # Fallback to formula on error
        logger.info("Falling back to formula confidence due to error")
        return await _calculate_formula_confidence(state, config)


async def calculate_confidence_node(state: AgentState) -> dict[str, Any]:
    """
    Node: Calculate confidence score for the response.

    Supports three calculation methods (configurable in database):
    - formula: Fast, algorithmic calculation based on retrieval metrics (free)
    - llm: Semantic evaluation using LLM (accurate, LLM cost per query)
    - hybrid: Combination of both (always calculates both and combines with weights)

    The method is determined by agent configuration in the database.

    Args:
        state: Current agent state

    Returns:
        Updated state with confidence_score, confidence_method, confidence_breakdown
    """
    try:
        logger.info("Calculating confidence score")

        # Load agent configuration for confidence calculation method
        agent_config = await get_active_config()

        if agent_config and hasattr(agent_config.config, "confidence_calculation"):
            calc_config = agent_config.config.confidence_calculation
            method = calc_config.method

            # Convert Pydantic models to dict for helper functions
            config_dict = {
                "method": method,
                "hybrid_settings": {
                    "formula_weight": calc_config.hybrid_settings.formula_weight,
                    "llm_weight": calc_config.hybrid_settings.llm_weight,
                },
                "llm_settings": {
                    "provider": calc_config.llm_settings.provider,
                    "model": calc_config.llm_settings.model,
                    "temperature": calc_config.llm_settings.temperature,
                    "max_tokens": calc_config.llm_settings.max_tokens,
                    "timeout_ms": calc_config.llm_settings.timeout_ms,
                },
                "formula_weights": {
                    "similarity": calc_config.formula_weights.similarity,
                    "source_quality": calc_config.formula_weights.source_quality,
                    "response_length": calc_config.formula_weights.response_length,
                }
            }

            logger.debug(f"Using confidence method from database: {method}")
        else:
            # Fallback to formula if no config
            method = "formula"
            config_dict = {}
            logger.warning("No agent config found, using default formula method")

        # Route to appropriate calculation method
        if method == "formula":
            result = await _calculate_formula_confidence(state, config_dict)
        elif method == "llm":
            result = await _calculate_llm_confidence(state, config_dict)
        elif method == "hybrid":
            result = await _calculate_hybrid_confidence(state, config_dict)
        else:
            logger.error(f"Unknown confidence method: {method}, falling back to formula")
            result = await _calculate_formula_confidence(state, config_dict)

        return result

    except Exception as e:
        logger.error(f"Confidence calculation failed: {e}", exc_info=True)
        return {
            "confidence_score": 0.0,
            "confidence_method": "error",
            "confidence_breakdown": {"error": str(e)}
        }


async def decision_node(state: AgentState) -> dict[str, Any]:
    """
    Node: Decide whether to return response or escalate to human.

    Based on confidence threshold from database configuration.

    Args:
        state: Current agent state

    Returns:
        Updated state with escalated flag and reason
    """
    try:
        confidence = state.get("confidence_score", 0.0)

        # Load agent configuration for threshold
        agent_config = await get_active_config()
        if agent_config:
            threshold = agent_config.config.confidence_thresholds.escalation
            logger.debug(
                f"Using database config threshold: {threshold:.2f} "
                f"(config v{agent_config.version})"
            )
        else:
            # Fallback to settings
            threshold = settings.agent_confidence_threshold
            logger.warning("Using fallback threshold (config not available)")

        logger.info(f"Decision: confidence={confidence:.2f}, threshold={threshold:.2f}")

        if confidence >= threshold:
            # High confidence - return response
            return {
                "escalated": False,
                "escalation_reason": None,
            }
        else:
            # Low confidence - escalate to human
            return {
                "escalated": True,
                "escalation_reason": f"Confidence score ({confidence:.2f}) below threshold ({threshold:.2f})",
            }

    except Exception as e:
        logger.error(f"Decision failed: {e}", exc_info=True)
        return {
            "escalated": True,
            "escalation_reason": f"Decision error: {str(e)}",
        }


def extract_relevant_excerpt(content: str, query: str, max_length: int = 300) -> str:
    """
    Extract the most relevant excerpt from content based on query keywords.
    
    Finds the sentence or paragraph that best matches the query and returns
    it with some surrounding context.
    
    Args:
        content: Full content text
        query: User's query to match against
        max_length: Maximum length of excerpt to return
        
    Returns:
        Most relevant excerpt from the content
    """
    if not content or not query:
        # Fallback to first portion if no query
        return content[:max_length] + ("..." if len(content) > max_length else "")
    
    # Extract keywords from query (remove common stop words)
    stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should', 'may', 'might', 'must', 'can', 'what', 'when', 'where', 'who', 'why', 'how', 'which', 'that', 'this', 'these', 'those'}
    query_words = set(re.findall(r'\b\w+\b', query.lower()))
    query_words = query_words - stop_words
    
    if not query_words:
        # If no meaningful keywords, return first portion
        return content[:max_length] + ("..." if len(content) > max_length else "")
    
    # Split content into sentences
    sentences = re.split(r'(?<=[.!?])\s+', content)
    
    # Score each sentence based on keyword matches
    scored_sentences = []
    for i, sentence in enumerate(sentences):
        sentence_lower = sentence.lower()
        # Count keyword matches (weighted by word length - longer words are more specific)
        matches = sum(len(word) for word in query_words if word in sentence_lower)
        if matches > 0:
            scored_sentences.append((i, sentence, matches))
    
    if not scored_sentences:
        # No matches found, return first portion
        return content[:max_length] + ("..." if len(content) > max_length else "")
    
    # Sort by match score (descending)
    scored_sentences.sort(key=lambda x: x[2], reverse=True)
    
    # Get the best matching sentence
    best_idx, best_sentence, _ = scored_sentences[0]
    
    # Try to include surrounding context (1 sentence before and after)
    start_idx = max(0, best_idx - 1)
    end_idx = min(len(sentences), best_idx + 2)
    
    excerpt = ' '.join(sentences[start_idx:end_idx])
    
    # Truncate if too long, but try to keep it meaningful
    if len(excerpt) > max_length:
        # Try to truncate at a sentence boundary
        truncated = excerpt[:max_length]
        last_period = truncated.rfind('.')
        last_exclamation = truncated.rfind('!')
        last_question = truncated.rfind('?')
        last_sentence_end = max(last_period, last_exclamation, last_question)
        
        if last_sentence_end > max_length * 0.7:  # Only if we're keeping most of it
            excerpt = truncated[:last_sentence_end + 1] + "..."
        else:
            excerpt = truncated + "..."
    
    return excerpt


async def format_output_node(state: AgentState) -> dict[str, Any]:
    """
    Node: Format final output with sources and metadata.

    Prepares the final response structure.

    Args:
        state: Current agent state

    Returns:
        Updated state with formatted sources
    """
    try:
        logger.info("Formatting output")

        # Get query for extracting relevant excerpts
        query = state.get("query", "")
        
        # First pass: collect all documents and their best matches
        # Use a dict to deduplicate by document title, keeping the best match (highest similarity)
        source_map = {}  # key: display_name, value: source dict with best similarity
        
        for doc in state.get("context_documents", []):
            # Get document title/filename from search results (preferred)
            document_title = doc.get("document_title") or doc.get("document_filename")
            
            # Fallback: Extract from chunk title if document info not available
            if not document_title:
                chunk_title = doc.get("title", "")
                # Remove " (chunk X/Y)" suffix to get filename
                document_title = chunk_title.split(" (chunk")[0] if chunk_title else None
            
            # Clean up the name for display
            if document_title:
                # Remove file extension for cleaner display
                display_name = document_title.rsplit('.', 1)[0] if '.' in document_title else document_title
                # Replace underscores with spaces
                display_name = display_name.replace('_', ' ')
                # Remove temporary file prefixes (tmp, temp, etc.)
                if display_name.lower().startswith('tmp'):
                    # Try to get a better name from metadata
                    metadata = doc.get("metadata", {})
                    original_file = metadata.get("original_file")
                    if original_file:
                        display_name = original_file.rsplit('.', 1)[0].replace('_', ' ')
                    else:
                        display_name = "Uploaded Document"
                # Capitalize words for better readability
                display_name = ' '.join(word.capitalize() for word in display_name.split())
            else:
                # Final fallback - use chunk ID to make it unique
                chunk_id = doc.get("id", "")
                source_type = doc.get("source", "unknown")
                display_name = source_type.replace("_", " ").title()
                if chunk_id:
                    # Make it unique by appending a portion of the ID
                    display_name = f"{display_name} ({chunk_id[:8]})"
            
            # Extract relevant excerpt that explains why it matched
            full_content = doc.get("content", "")
            relevant_excerpt = extract_relevant_excerpt(full_content, query, max_length=300)
            similarity = doc.get("similarity", 0.0)
            
            # Create source entry
            source_entry = {
                "content": relevant_excerpt,  # Show why it matched, not just start of chunk
                "source": display_name,  # Clean, readable document name
                "timestamp": doc.get("timestamp") or doc.get("doc_timestamp"),
                "metadata": doc.get("metadata", {}),
                "similarity_score": similarity,
            }
            
            # Deduplicate: keep only the best match (highest similarity) for each document
            if display_name not in source_map:
                source_map[display_name] = source_entry
            else:
                # Replace if this match has higher similarity
                if similarity > source_map[display_name]["similarity_score"]:
                    source_map[display_name] = source_entry
        
        # Convert map to list, sorted by similarity (descending)
        sources = list(source_map.values())
        sources.sort(key=lambda x: x["similarity_score"], reverse=True)

        return {"sources": sources}

    except Exception as e:
        logger.error(f"Output formatting failed: {e}", exc_info=True)
        return {"sources": []}

# ============================================================================
# Tool Invocation Nodes
# ============================================================================

async def invoke_tools_node(state: AgentState) -> dict[str, Any]:
    """
    Node: Invoke tools based on query requirements.

    Executes necessary tools (calculator, web search, etc.) and returns results.

    Args:
        state: Current agent state

    Returns:
        Updated state with tool results
    """
    try:
        logger.info("Invoking tools")

        query_analysis = state.get("query_analysis")
        query = state["query"]

        # Get tool registry
        tool_registry = get_tool_registry()

        # Get available tools (built-in + MCP)
        built_in_tools = tool_registry.get_all_tools(enabled_only=True)

        # Get MCP tools if available
        mcp_manager = get_mcp_client_manager()
        mcp_tools = await mcp_manager.get_tools()

        all_tools = built_in_tools + mcp_tools

        logger.info(f"Available tools: {len(built_in_tools)} built-in, {len(mcp_tools)} MCP")

        if not all_tools:
            logger.warning("No tools available for invocation")
            return {
                "tool_results": [],
                "tool_invocation_error": "No tools available"
            }

        # Load agent configuration for model settings
        agent_config = await get_active_config()
        if agent_config:
            model_settings = agent_config.config.model_settings
            provider = model_settings.provider
            model = model_settings.model
        else:
            provider = "openai"
            model = settings.openai_model

        # Get chat model with tools bound
        chat_model = get_chat_model(
            provider=provider,
            model=model,
            temperature=0.3,  # Lower temperature for tool calling
        )

        # Bind tools to model
        model_with_tools = chat_model.bind_tools(all_tools)

        # Load tool invocation prompt from database
        system_prompt, tool_version = await get_formatted_prompt(
            name="tool_invocation_system",
            prompt_type="tool_invocation",
            variables={},
            fallback="You are a helpful assistant with access to tools. Analyze the user's query and determine which tools to use, if any. Call the appropriate tools with the correct arguments."
        )
        logger.info(f"Using tool invocation prompt v{tool_version if tool_version else 'fallback'}")

        # Invoke model to get tool calls
        response = await model_with_tools.ainvoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=query)
        ])

        tool_results = []

        # Execute tool calls if any
        if hasattr(response, 'tool_calls') and response.tool_calls:
            logger.info(f"Model requested {len(response.tool_calls)} tool calls")

            for tool_call in response.tool_calls:
                tool_name = tool_call.get("name")
                tool_args = tool_call.get("args", {})
                tool_id = tool_call.get("id")

                logger.info(f"Executing tool: {tool_name} with args: {tool_args}")

                try:
                    # Find the tool
                    tool = None
                    for t in all_tools:
                        if t.name == tool_name:
                            tool = t
                            break

                    if not tool:
                        raise ValueError(f"Tool '{tool_name}' not found")

                    # Execute the tool
                    result = await tool.ainvoke(tool_args)

                    tool_results.append({
                        "tool_name": tool_name,
                        "tool_args": tool_args,
                        "tool_id": tool_id,
                        "result": result,
                        "success": True
                    })

                    logger.info(f"Tool {tool_name} executed successfully")

                except Exception as e:
                    error_msg = f"Tool execution error: {str(e)}"
                    logger.error(f"Tool {tool_name} failed: {error_msg}", exc_info=True)

                    tool_results.append({
                        "tool_name": tool_name,
                        "tool_args": tool_args,
                        "tool_id": tool_id,
                        "result": error_msg,
                        "success": False,
                        "error": str(e)
                    })

        else:
            logger.info("No tool calls requested by model")

        return {"tool_results": tool_results}

    except Exception as e:
        logger.error(f"Tool invocation failed: {e}", exc_info=True)
        return {
            "tool_results": [],
            "tool_invocation_error": f"Tool invocation error: {str(e)}"
        }


async def route_decision_node(state: AgentState) -> str:
    """
    Node: Determine routing path based on query analysis.

    Returns the name of the next node to execute.

    Args:
        state: Current agent state

    Returns:
        Next node name
    """
    query_analysis = state.get("query_analysis")

    if not query_analysis:
        logger.warning("No query analysis available - defaulting to standard RAG")
        return "retrieve_context"

    routing = query_analysis.routing

    logger.info(f"Routing decision: {routing}")

    if routing == RoutingDecision.TOOL_INVOCATION:
        return "invoke_tools"
    elif routing == RoutingDecision.MULTI_STEP_REASONING:
        # For now, treat multi-step as standard RAG
        # In future, this could trigger a more complex reasoning loop
        return "retrieve_context"
    elif routing == RoutingDecision.DIRECT_ESCALATION:
        # Skip to response generation with escalation flag
        return "generate_response"
    elif routing == RoutingDecision.CACHED_RESPONSE:
        # TODO: Implement semantic cache check
        # For now, proceed with standard RAG
        return "retrieve_context"
    else:  # STANDARD_RAG
        return "retrieve_context"
