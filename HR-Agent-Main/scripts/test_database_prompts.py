"""
Test that all prompts are correctly loaded from database.
"""

import asyncio
from app.services.prompts import get_active_prompt, get_formatted_prompt
from app.core.logging import get_logger

logger = get_logger(__name__)


async def test_all_prompts():
    """Test all active prompts can be loaded from database."""
    print("\n" + "="*80)
    print("DATABASE PROMPTS TEST")
    print("="*80 + "\n")

    prompts_to_test = [
        ("query_analysis_system", "query_analysis_system"),
        ("query_analysis_user", "analysis"),
        ("main_system_prompt", "system"),
        ("retrieval_context_prompt", "retrieval"),
        ("confidence_evaluation_prompt", "confidence"),
        ("tool_invocation_system", "tool_invocation"),
    ]

    success_count = 0
    fail_count = 0

    for name, prompt_type in prompts_to_test:
        try:
            print(f"\nTesting: {name} (type: {prompt_type})")
            print("-" * 80)

            prompt_obj = await get_active_prompt(name=name, prompt_type=prompt_type)

            if prompt_obj:
                print(f"[SUCCESS] Loaded from database")
                print(f"  Version: {prompt_obj.version}")
                print(f"  Content length: {len(prompt_obj.content)} chars")
                print(f"  Preview: {prompt_obj.content[:100]}...")
                success_count += 1
            else:
                print(f"[WARNING] Prompt not found in database (will use fallback)")
                fail_count += 1

        except Exception as e:
            print(f"[ERROR] Failed to load: {e}")
            fail_count += 1

    # Test formatted prompt with variables
    print("\n\n" + "="*80)
    print("TESTING FORMATTED PROMPT WITH VARIABLES")
    print("="*80 + "\n")

    try:
        variables = {
            "query": "What is PCI DSS?",
            "products": "payment api, payment sdk",
            "payment_methods": "credit card, ACH",
            "concepts": "compliance, security",
            "technical_terms": "API, webhook",
        }

        formatted, version = await get_formatted_prompt(
            name="query_analysis_user",
            prompt_type="analysis",
            variables=variables,
            fallback="FALLBACK PROMPT"
        )

        print(f"[SUCCESS] Formatted prompt loaded")
        print(f"  Version: {version}")
        print(f"  Length: {len(formatted)} chars")
        print(f"  Variables replaced: {all(v in formatted for v in ['PCI DSS', 'payment api'])}")
        print(f"\n  Preview:\n{formatted[:300]}...")

    except Exception as e:
        print(f"[ERROR] Failed to format: {e}")
        fail_count += 1

    # Summary
    print("\n\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    print(f"\n  Total prompts tested: {len(prompts_to_test)}")
    print(f"  Successful loads: {success_count}")
    print(f"  Failures/Fallbacks: {fail_count}")

    if fail_count == 0:
        print(f"\n  [SUCCESS] All prompts loaded from database!")
    else:
        print(f"\n  [WARNING] Some prompts will use fallbacks")

    print("\n" + "="*80 + "\n")


async def main():
    """Run all tests."""
    try:
        await test_all_prompts()
    except Exception as e:
        print(f"\n[ERROR] Test failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
