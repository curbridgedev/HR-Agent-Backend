"""
Seed database with sample documents for testing RAG system.
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db.supabase import get_supabase_client
from app.services.embedding import generate_embeddings_batch
from app.core.config import settings
from app.core.logging import setup_logging, get_logger

setup_logging()
logger = get_logger(__name__)

# Sample documents about Compaytence (replace with real data)
SAMPLE_DOCUMENTS = [
    {
        "title": "What is Compaytence?",
        "content": """Compaytence is an AI-powered platform for finance and payment operations.
        It provides 24/7 intelligent assistance for payment-related queries, helping teams
        quickly find information from multiple sources including Slack, WhatsApp, and Telegram.
        The platform uses advanced RAG (Retrieval-Augmented Generation) to provide accurate
        answers with high confidence scores.""",
        "source": "admin_upload",
        "metadata": {"type": "overview", "category": "product"},
    },
    {
        "title": "Compaytence Features",
        "content": """Compaytence offers several key features:
        1. Multi-source data ingestion from Slack, WhatsApp, and Telegram
        2. Intelligent document processing with table preservation
        3. 95% confidence threshold for automated responses
        4. Human escalation for low-confidence queries
        5. White-label chat portal and embeddable widget
        6. Admin dashboard for system management and prompt configuration""",
        "source": "admin_upload",
        "metadata": {"type": "features", "category": "product"},
    },
    {
        "title": "How Compaytence Works",
        "content": """Compaytence works by ingesting knowledge from your existing communication
        channels and documents. When a user asks a question, the system:
        1. Searches the vector database for relevant context
        2. Uses AI to generate a response based on that context
        3. Calculates a confidence score for the response
        4. Returns the answer if confidence is above 95%, otherwise escalates to human
        This ensures accurate, context-aware responses while maintaining quality.""",
        "source": "admin_upload",
        "metadata": {"type": "how-it-works", "category": "technical"},
    },
    {
        "title": "Payment Processing Information",
        "content": """Compaytence helps teams manage payment operations efficiently.
        The platform can answer questions about payment status, transaction details,
        refund policies, and payment methods. It integrates with your existing
        knowledge base to provide instant, accurate answers to payment-related queries,
        reducing support ticket volume and improving response times.""",
        "source": "admin_upload",
        "metadata": {"type": "payments", "category": "use-case"},
    },
    {
        "title": "Finance Team Support",
        "content": """For finance teams, Compaytence provides instant access to information
        about invoices, reconciliation processes, financial reporting, and compliance
        requirements. The AI agent can quickly retrieve relevant financial policies,
        procedures, and historical data from your communication channels and documents,
        enabling faster decision-making and reducing time spent searching for information.""",
        "source": "admin_upload",
        "metadata": {"type": "finance", "category": "use-case"},
    },
]


async def seed_documents():
    """Seed the database with sample documents."""
    try:
        logger.info("Starting database seeding...")

        # Get Supabase client
        db = get_supabase_client()

        # Check if documents already exist
        existing = db.table("documents").select("id").limit(1).execute()
        if existing.data:
            logger.warning("Documents already exist. Skipping seed.")
            print("\n⚠️  Database already has documents. Skipping seed.")
            print("To re-seed, delete existing documents first.")
            return

        # Generate embeddings for all documents
        logger.info("Generating embeddings for sample documents...")
        texts = [doc["content"] for doc in SAMPLE_DOCUMENTS]
        embeddings = await generate_embeddings_batch(texts)

        # Insert documents with embeddings
        logger.info("Inserting documents into database...")
        for i, doc in enumerate(SAMPLE_DOCUMENTS):
            document_data = {
                "title": doc["title"],
                "content": doc["content"],
                "embedding": embeddings[i],
                "source": doc["source"],
                "metadata": doc["metadata"],
                "processing_status": "completed",
            }

            result = db.table("documents").insert(document_data).execute()

            if result.data:
                logger.info(f"✅ Inserted: {doc['title']}")
                print(f"✅ Inserted: {doc['title']}")
            else:
                logger.error(f"❌ Failed to insert: {doc['title']}")

        logger.info("Database seeding completed successfully!")
        print(f"\n🎉 Successfully seeded {len(SAMPLE_DOCUMENTS)} documents!")
        print("\nYou can now test the chat endpoint with questions like:")
        print("  - 'What is Compaytence?'")
        print("  - 'How does Compaytence work?'")
        print("  - 'What features does Compaytence offer?'")

    except Exception as e:
        logger.error(f"Seeding failed: {e}", exc_info=True)
        print(f"\n❌ Error seeding database: {e}")
        print("\nMake sure:")
        print("1. Supabase migration has been run (001_initial_schema.sql)")
        print("2. Environment variables are set correctly (.env)")
        print("3. pgvector extension is enabled in Supabase")


if __name__ == "__main__":
    print("🌱 Seeding Compaytence Database...")
    print("=" * 50)
    asyncio.run(seed_documents())
