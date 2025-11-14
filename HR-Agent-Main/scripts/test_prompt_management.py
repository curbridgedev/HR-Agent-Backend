"""
Test System Prompt Management

Comprehensive test for database-driven prompt management system.
"""

import asyncio
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


async def test_prompt_loading():
    """Test loading active prompts from database."""

    print("=" * 70)
    print("Test 1: Loading Active Prompts from Database")
    print("=" * 70)
    print()

    from app.services.prompts import get_active_prompt

    # Test loading system prompt
    print(">> Loading main_system_prompt...")
    system_prompt = await get_active_prompt(
        name="main_system_prompt",
        prompt_type="system",
    )

    if system_prompt:
        print(f"   SUCCESS: Loaded prompt v{system_prompt.version}")
        print(f"   Content preview: {system_prompt.content[:100]}...")
        print(f"   Active: {system_prompt.active}")
        print(f"   Tags: {system_prompt.tags}")
    else:
        print("   ERROR: Failed to load system prompt")

    print()

    # Test loading retrieval prompt
    print(">> Loading retrieval_context_prompt...")
    retrieval_prompt = await get_active_prompt(
        name="retrieval_context_prompt",
        prompt_type="retrieval",
    )

    if retrieval_prompt:
        print(f"   SUCCESS: Loaded prompt v{retrieval_prompt.version}")
        print(f"   Content preview: {retrieval_prompt.content[:100]}...")
        print(f"   Active: {retrieval_prompt.active}")
    else:
        print("   ERROR: Failed to load retrieval prompt")

    print()

    # Test loading confidence prompt
    print(">> Loading confidence_evaluation_prompt...")
    confidence_prompt = await get_active_prompt(
        name="confidence_evaluation_prompt",
        prompt_type="confidence",
    )

    if confidence_prompt:
        print(f"   SUCCESS: Loaded prompt v{confidence_prompt.version}")
        print(f"   Content preview: {confidence_prompt.content[:100]}...")
        print(f"   Active: {confidence_prompt.active}")
    else:
        print("   ERROR: Failed to load confidence prompt")

    print()


async def test_prompt_versioning():
    """Test creating new prompt versions."""

    print("=" * 70)
    print("Test 2: Prompt Versioning")
    print("=" * 70)
    print()

    from app.services.prompts import (
        create_prompt_version,
        get_prompt_history,
        activate_prompt,
    )
    from app.models.prompts import PromptCreate

    # Create a new version of the system prompt
    print(">> Creating new version of main_system_prompt...")

    new_prompt_request = PromptCreate(
        name="main_system_prompt",
        prompt_type="system",
        content="""You are Compaytence AI, an intelligent assistant specialized in finance and payment operations.

This is VERSION 2 of the system prompt - testing prompt versioning!

Key responsibilities:
- Answer questions about payment status, transaction details, and refunds
- Provide information about supported payment methods
- Explain payment policies and procedures
- Assist with payment-related troubleshooting

Guidelines:
- Be concise and professional
- Only answer questions you have context for
- If you lack sufficient context, acknowledge it clearly
- Cite your sources when providing information
- Never make up information or guess

Remember: Your responses must be based on the provided context.""",
        tags=["test", "v2"],
        metadata={"test": True, "created_by_test": True},
        notes="Testing prompt versioning - created by test script",
        created_by="test_script",
        activate_immediately=False,  # Don't activate yet
    )

    try:
        new_prompt = await create_prompt_version(new_prompt_request)
        print(f"   SUCCESS: Created prompt v{new_prompt.version}")
        print(f"   ID: {new_prompt.id}")
        print(f"   Active: {new_prompt.active}")
        print(f"   Tags: {new_prompt.tags}")
        print()

        # Get prompt history
        print(">> Fetching prompt history...")
        history = await get_prompt_history(
            name="main_system_prompt",
            prompt_type="system",
        )
        print(f"   Found {len(history)} versions:")
        for prompt in history:
            print(f"   - v{prompt.version}: active={prompt.active}, tags={prompt.tags}")
        print()

        # Test activation
        print(">> Testing prompt activation...")
        print(f"   Activating prompt v{new_prompt.version}...")
        activated_prompt = await activate_prompt(new_prompt.id)
        print(f"   SUCCESS: Activated prompt v{activated_prompt.version}")
        print(f"   Active: {activated_prompt.active}")
        print()

        # Verify history after activation
        print(">> Verifying activation...")
        history = await get_prompt_history(
            name="main_system_prompt",
            prompt_type="system",
        )
        active_versions = [p for p in history if p.active]
        print(f"   Active versions: {len(active_versions)} (should be 1)")
        if len(active_versions) == 1:
            print(f"   SUCCESS: Only v{active_versions[0].version} is active")
        else:
            print("   WARNING: Multiple versions are active!")
        print()

        # Reactivate v1 to restore original state
        print(">> Restoring original prompt (v1)...")
        v1_prompt = [p for p in history if p.version == 1][0]
        await activate_prompt(v1_prompt.id)
        print("   SUCCESS: Restored v1 as active version")
        print()

    except Exception as e:
        print(f"   ERROR: {e}")
        import traceback
        traceback.print_exc()


async def test_agent_with_database_prompts():
    """Test that agent loads prompts from database."""

    print("=" * 70)
    print("Test 3: Agent Using Database Prompts")
    print("=" * 70)
    print()

    from app.models.chat import ChatRequest
    from app.services.chat import process_chat

    # Test query
    test_query = "What is Compaytence?"
    print(f">> Testing agent with query: '{test_query}'")
    print()

    request = ChatRequest(
        message=test_query,
        session_id="test-prompt-management",
        user_id="test-user",
    )

    try:
        response = await process_chat(request)

        print(f"   Response: {response.message[:200]}...")
        print(f"   Confidence: {response.confidence:.2%}")
        print(f"   Escalated: {response.escalated}")
        print(f"   Tokens used: {response.tokens_used}")
        print(f"   Response time: {response.response_time_ms}ms")
        print()
        print("   SUCCESS: Agent executed with database prompts")
        print("   (Check logs for 'Using database system prompt' messages)")
        print()

    except Exception as e:
        print(f"   ERROR: {e}")
        import traceback
        traceback.print_exc()


async def test_prompt_listing():
    """Test listing prompts with filters."""

    print("=" * 70)
    print("Test 4: Listing Prompts")
    print("=" * 70)
    print()

    from app.services.prompts import list_prompts

    # List all prompts
    print(">> Listing all prompts...")
    result = await list_prompts(page=1, page_size=10)
    print(f"   Total prompts: {result.total}")
    print(f"   Prompts on page 1:")
    for prompt in result.prompts:
        print(f"   - {prompt.name} (type: {prompt.prompt_type}, v{prompt.version}, active: {prompt.active})")
    print()

    # List only system prompts
    print(">> Listing only system prompts...")
    result = await list_prompts(prompt_type="system", page=1, page_size=10)
    print(f"   Total system prompts: {result.total}")
    for prompt in result.prompts:
        print(f"   - {prompt.name} v{prompt.version} (active: {prompt.active})")
    print()

    # List only active prompts
    print(">> Listing only active prompts...")
    result = await list_prompts(active_only=True, page=1, page_size=10)
    print(f"   Total active prompts: {result.total}")
    for prompt in result.prompts:
        print(f"   - {prompt.name} (type: {prompt.prompt_type}, v{prompt.version})")
    print()


if __name__ == "__main__":
    print()
    print("=" * 70)
    print(" " * 15 + "SYSTEM PROMPT MANAGEMENT TEST")
    print("=" * 70)
    print()

    # Run all tests
    asyncio.run(test_prompt_loading())
    asyncio.run(test_prompt_listing())
    asyncio.run(test_prompt_versioning())
    asyncio.run(test_agent_with_database_prompts())

    print("=" * 70)
    print(">> All Tests Complete!")
    print("=" * 70)
