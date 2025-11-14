"""
Test Agent Configuration System

Comprehensive test for database-driven agent configuration with versioning,
environment-specific configs, and caching.
"""

import asyncio
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


async def test_config_loading():
    """Test loading active configurations from database."""

    print("=" * 70)
    print("Test 1: Loading Active Configurations")
    print("=" * 70)
    print()

    from app.services.agent_config import get_active_config
    from app.core.config import settings

    # Test loading default config
    print(f">> Current environment: {settings.environment}")
    print()

    print(">> Loading default config for current environment...")
    config = await get_active_config()

    if config:
        print(f"   SUCCESS: Loaded config v{config.version}")
        print(f"   Environment: {config.environment}")
        print(f"   Active: {config.active}")
        print(f"   Description: {config.description}")
        print()
        print(f"   Confidence Thresholds:")
        print(f"     - Escalation: {config.config.confidence_thresholds.escalation}")
        print(f"     - High: {config.config.confidence_thresholds.high}")
        print(f"     - Medium: {config.config.confidence_thresholds.medium}")
        print(f"     - Low: {config.config.confidence_thresholds.low}")
        print()
        print(f"   Model Settings:")
        print(f"     - Model: {config.config.model_settings.model}")
        print(f"     - Temperature: {config.config.model_settings.temperature}")
        print(f"     - Max Tokens: {config.config.model_settings.max_tokens}")
        print()
        print(f"   Search Settings:")
        print(f"     - Similarity Threshold: {config.config.search_settings.similarity_threshold}")
        print(f"     - Max Results: {config.config.search_settings.max_results}")
        print(f"     - Hybrid Search: {config.config.search_settings.use_hybrid_search}")
        print()
        print(f"   Feature Flags:")
        print(f"     - PII Anonymization: {config.config.feature_flags.enable_pii_anonymization}")
        print(f"     - Semantic Cache: {config.config.feature_flags.enable_semantic_cache}")
        print(f"     - Query Rewriting: {config.config.feature_flags.enable_query_rewriting}")
        print()
    else:
        print("   ERROR: Failed to load config")

    print()


async def test_environment_configs():
    """Test loading environment-specific configurations."""

    print("=" * 70)
    print("Test 2: Environment-Specific Configurations")
    print("=" * 70)
    print()

    from app.services.agent_config import get_active_config

    environments = ["development", "production", "all"]

    for env in environments:
        print(f">> Loading config for environment: {env}")
        config = await get_active_config(environment=env)

        if config:
            print(f"   Config: {config.name} v{config.version} (env: {config.environment})")
            print(f"   Escalation threshold: {config.config.confidence_thresholds.escalation}")
            print(f"   Max tokens: {config.config.model_settings.max_tokens}")
            print(f"   Semantic cache: {config.config.feature_flags.enable_semantic_cache}")
        else:
            print(f"   WARNING: No config found for {env}")

        print()


async def test_config_caching():
    """Test configuration caching."""

    print("=" * 70)
    print("Test 3: Configuration Caching")
    print("=" * 70)
    print()

    from app.services.agent_config import get_active_config, clear_config_cache
    import time

    print(">> First load (should hit database)...")
    start = time.time()
    config1 = await get_active_config()
    time1 = (time.time() - start) * 1000
    print(f"   Load time: {time1:.2f}ms")
    print(f"   Config: {config1.name if config1 else 'None'}")
    print()

    print(">> Second load (should hit cache)...")
    start = time.time()
    config2 = await get_active_config()
    time2 = (time.time() - start) * 1000
    print(f"   Load time: {time2:.2f}ms")
    print(f"   Config: {config2.name if config2 else 'None'}")
    print()

    if time2 < time1:
        speedup = (time1 / time2)
        print(f"   SUCCESS: Cache speedup: {speedup:.1f}x faster")
    else:
        print("   WARNING: Cache may not be working properly")

    print()

    print(">> Clearing cache...")
    clear_config_cache()
    print("   Cache cleared")
    print()

    print(">> Third load (should hit database again)...")
    start = time.time()
    config3 = await get_active_config()
    time3 = (time.time() - start) * 1000
    print(f"   Load time: {time3:.2f}ms")
    print()


async def test_config_versioning():
    """Test creating new config versions."""

    print("=" * 70)
    print("Test 4: Configuration Versioning")
    print("=" * 70)
    print()

    from app.services.agent_config import (
        create_config_version,
        get_config_history,
        activate_config,
    )
    from app.models.agent_config import (
        AgentConfigCreate,
        AgentConfigData,
        ConfidenceThresholds,
        ModelSettings,
        SearchSettings,
        ToolRegistry,
        FeatureFlags,
        RateLimits,
    )

    # Create a new config version with modified settings
    print(">> Creating new config version with test settings...")

    test_config = AgentConfigData(
        confidence_thresholds=ConfidenceThresholds(
            escalation=0.92,
            high=0.82,
            medium=0.67,
            low=0.47,
        ),
        model_settings=ModelSettings(
            model="gpt-4",
            temperature=0.8,
            max_tokens=1200,
        ),
        search_settings=SearchSettings(
            similarity_threshold=0.72,
            max_results=8,
            use_hybrid_search=True,
        ),
        tool_registry=ToolRegistry(),
        feature_flags=FeatureFlags(
            enable_semantic_cache=True,
            enable_query_rewriting=True,
        ),
        rate_limits=RateLimits(),
    )

    new_config_request = AgentConfigCreate(
        name="default_agent_config",
        environment="development",
        config=test_config,
        description="Test configuration v2 with modified settings",
        tags=["test", "v2"],
        notes="Testing config versioning - created by test script",
        created_by="test_script",
        activate_immediately=False,  # Don't activate yet
    )

    try:
        new_config = await create_config_version(new_config_request)
        print(f"   SUCCESS: Created config v{new_config.version}")
        print(f"   ID: {new_config.id}")
        print(f"   Active: {new_config.active}")
        print(f"   Escalation threshold: {new_config.config.confidence_thresholds.escalation}")
        print(f"   Temperature: {new_config.config.model_settings.temperature}")
        print()

        # Get config history
        print(">> Fetching config history for development environment...")
        history = await get_config_history(
            name="default_agent_config",
            environment="development",
        )
        print(f"   Found {len(history)} versions:")
        for cfg in history:
            print(f"   - v{cfg.version}: active={cfg.active}, tags={cfg.tags}")
        print()

        # Test activation
        print(">> Testing config activation...")
        print(f"   Activating config v{new_config.version}...")
        activated_config = await activate_config(new_config.id)
        print(f"   SUCCESS: Activated config v{activated_config.version}")
        print()

        # Verify activation
        print(">> Verifying activation...")
        history = await get_config_history(
            name="default_agent_config",
            environment="development",
        )
        active_versions = [c for c in history if c.active]
        print(f"   Active versions: {len(active_versions)} (should be 1)")
        if len(active_versions) == 1:
            print(f"   SUCCESS: Only v{active_versions[0].version} is active")
        else:
            print("   WARNING: Multiple versions are active!")
        print()

        # Reactivate original v1
        print(">> Restoring original config (v1)...")
        v1_config = [c for c in history if c.version == 1][0]
        await activate_config(v1_config.id)
        print("   SUCCESS: Restored v1 as active version")
        print()

    except Exception as e:
        print(f"   ERROR: {e}")
        import traceback
        traceback.print_exc()


async def test_agent_with_config():
    """Test that agent uses database configuration."""

    print("=" * 70)
    print("Test 5: Agent Using Database Configuration")
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
        session_id="test-agent-config",
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
        print("   SUCCESS: Agent executed with database configuration")
        print("   (Check logs for 'Using database config' messages)")
        print()

    except Exception as e:
        print(f"   ERROR: {e}")
        import traceback
        traceback.print_exc()


async def test_config_listing():
    """Test listing configurations."""

    print("=" * 70)
    print("Test 6: Listing Configurations")
    print("=" * 70)
    print()

    from app.services.agent_config import list_configs

    # List all configs
    print(">> Listing all configs...")
    result = await list_configs(page=1, page_size=10)
    print(f"   Total configs: {result.total}")
    print(f"   Configs on page 1:")
    for cfg in result.configs:
        print(f"   - {cfg.name} (env: {cfg.environment}, v{cfg.version}, active: {cfg.active})")
    print()

    # List only development configs
    print(">> Listing only development configs...")
    result = await list_configs(environment="development", page=1, page_size=10)
    print(f"   Total development configs: {result.total}")
    for cfg in result.configs:
        print(f"   - {cfg.name} v{cfg.version} (active: {cfg.active})")
    print()

    # List only active configs
    print(">> Listing only active configs...")
    result = await list_configs(active_only=True, page=1, page_size=10)
    print(f"   Total active configs: {result.total}")
    for cfg in result.configs:
        print(f"   - {cfg.name} (env: {cfg.environment}, v{cfg.version})")
    print()


if __name__ == "__main__":
    print()
    print("=" * 70)
    print(" " * 15 + "AGENT CONFIGURATION SYSTEM TEST")
    print("=" * 70)
    print()

    # Run all tests
    asyncio.run(test_config_loading())
    asyncio.run(test_environment_configs())
    asyncio.run(test_config_caching())
    asyncio.run(test_config_listing())
    asyncio.run(test_config_versioning())
    asyncio.run(test_agent_with_config())

    print("=" * 70)
    print(">> All Tests Complete!")
    print("=" * 70)
