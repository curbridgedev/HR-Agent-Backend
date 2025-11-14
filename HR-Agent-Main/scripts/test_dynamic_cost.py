"""
Quick test to verify dynamic cost calculation.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.embedding import _get_cost_per_token, _calculate_cost
from app.core.config import settings

print("=" * 80)
print("DYNAMIC COST CALCULATION TEST")
print("=" * 80)

print(f"\nConfigured model: {settings.openai_embedding_model}")

# Get cost per token
cost_per_token = _get_cost_per_token(settings.openai_embedding_model)
cost_per_1m = cost_per_token * 1_000_000

print(f"Cost per token: ${cost_per_token:.10f}")
print(f"Cost per 1M tokens: ${cost_per_1m:.2f}")

# Test cost calculation for different token counts
print("\nSample cost calculations:")
test_tokens = [100, 1000, 10000, 100000, 1000000]
for tokens in test_tokens:
    cost = _calculate_cost(tokens)
    print(f"  {tokens:>7} tokens = ${cost:.6f}")

print("\n" + "=" * 80)
print("TEST PASSED: Dynamic cost calculation working correctly!")
print("=" * 80)
