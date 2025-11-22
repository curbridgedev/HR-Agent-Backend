"""
Configuration management using Pydantic Settings.
All environment variables are loaded and validated here.
"""

from typing import List, Literal
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    All configuration is environment-aware with zero code changes between Dev/UAT/Prod.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application Settings
    environment: Literal["development", "uat", "production"] = "development"
    app_name: str = "HR Agent - Canadian Employment Standards Assistant"
    app_version: str = "1.0.0"
    debug: bool = False
    log_level: str = "INFO"

    # API Configuration
    api_v1_prefix: str = "/api/v1"
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # CORS Settings
    cors_origins: str = "http://localhost:3000"
    cors_credentials: bool = True
    cors_methods: str = "GET,POST,PUT,DELETE,PATCH"
    cors_headers: str = "*"

    @property
    def cors_origins_list(self) -> List[str]:
        """Convert comma-separated CORS origins to list."""
        return [origin.strip() for origin in self.cors_origins.split(",")]

    @property
    def cors_methods_list(self) -> List[str]:
        """Convert comma-separated CORS methods to list."""
        return [method.strip() for method in self.cors_methods.split(",")]

    # Security & Authentication
    secret_key: str = Field(..., min_length=32)
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30
    jwt_refresh_token_expire_days: int = 7

    better_auth_url: str = ""
    better_auth_secret: str = ""

    api_key_header_name: str = "X-API-Key"
    internal_api_key: str = ""

    # Database - Supabase
    supabase_url: str = Field(..., description="Supabase project URL")
    supabase_anon_key: str = Field(..., description="Supabase anon key")
    supabase_service_role_key: str = Field(..., description="Supabase service role key")
    database_url: str = ""

    # Vector Search Configuration
    vector_similarity_threshold: float = 0.45  # Lowered to capture more relevant results (was 0.60)
    vector_max_results: int = 15  # Increased to get more candidates before filtering/reranking (was 5)
    hybrid_search_enabled: bool = True

    # AI & Language Models
    openai_api_key: str = Field(..., description="OpenAI API key")
    openai_model: str = "gpt-4"
    openai_embedding_model: str = "text-embedding-3-small"
    openai_embedding_dimensions: int = 1536  # Max 1536 for small, 3072 for large (pgvector limit: 2000)
    openai_max_tokens: int = 2000
    openai_temperature: float = 0.2

    # Cohere (Reranking)
    cohere_api_key: str = Field("", description="Cohere API key for reranking")
    cohere_rerank_model: str = "rerank-english-v3.0"
    cohere_enabled: bool = True

    # Tavily (Web Search)
    tavily_api_key: str = Field("", description="Tavily API key for web search")

    # Agent Configuration
    agent_confidence_threshold: float = 0.95
    agent_max_iterations: int = 5
    agent_timeout_seconds: int = 30
    agent_enable_streaming: bool = True

    # Conversation Memory Configuration
    conversation_history_max_messages: int = 20  # Max messages to include in context
    conversation_history_max_tokens: int = 4000  # Approximate token limit for history
    conversation_history_enabled: bool = True

    # Semantic Caching
    enable_semantic_cache: bool = True
    cache_similarity_threshold: float = 0.98
    cache_ttl_seconds: int = 3600

    # Observability - LangFuse
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "https://cloud.langfuse.com"
    langfuse_enabled: bool = True
    langfuse_sample_rate: float = 1.0
    langfuse_flush_interval: int = 10

    # Background Jobs - Inngest
    inngest_event_key: str = ""
    inngest_signing_key: str = ""
    inngest_env: str = "development"
    inngest_serve_path: str = "/api/inngest"
    inngest_max_retries: int = 3
    inngest_retry_delay_seconds: int = 60

    # Airtable Integration (HR Agent Escalations & Analytics)
    airtable_api_key: str = ""
    airtable_base_id: str = ""
    airtable_escalations_table: str = "Escalations"
    airtable_analytics_table: str = "Analytics"

    # Document Processing - Docling
    docling_enabled: bool = True
    docling_max_file_size_mb: int = 50
    docling_supported_formats: str = "pdf,docx,xlsx,pptx,txt,md"
    docling_ocr_enabled: bool = True
    docling_preserve_tables: bool = True

    @property
    def docling_supported_formats_list(self) -> List[str]:
        """Convert comma-separated formats to list."""
        return [fmt.strip() for fmt in self.docling_supported_formats.split(",")]

    # Chunking Configuration
    chunk_size: int = 1000
    chunk_overlap: int = 200
    enable_structure_aware_chunking: bool = True

    # Chat Platform Integrations
    slack_bot_token: str = ""
    slack_signing_secret: str = ""
    slack_app_token: str = ""
    slack_webhook_url: str = "/api/v1/webhooks/slack"

    whatsapp_business_account_id: str = ""
    whatsapp_access_token: str = ""
    whatsapp_phone_number_id: str = ""
    whatsapp_webhook_verify_token: str = ""
    whatsapp_webhook_url: str = "/api/v1/webhooks/whatsapp"

    telegram_bot_token: str = ""
    telegram_api_id: str = ""
    telegram_api_hash: str = ""
    telegram_webhook_url: str = "/api/v1/webhooks/telegram"
    telegram_session_string: str = ""
    telegram_phone_number: str = ""

    # Telegram Error Notifications
    telegram_error_bot_token: str = ""
    telegram_error_chat_id: str = ""
    telegram_error_thread_id: int = 0
    telegram_error_notifications_enabled: bool = True

    # File Storage & Uploads
    max_upload_size_mb: int = 50
    allowed_upload_extensions: str = "pdf,docx,xlsx,pptx,txt,md,csv"
    upload_temp_dir: str = "/tmp/uploads"
    storage_backend: Literal["supabase", "s3", "local"] = "supabase"
    storage_bucket: str = "hr-agent-documents"

    @property
    def allowed_upload_extensions_list(self) -> List[str]:
        """Convert comma-separated extensions to list."""
        return [ext.strip() for ext in self.allowed_upload_extensions.split(",")]

    # S3 Configuration (optional)
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    aws_region: str = "us-east-1"
    s3_bucket: str = ""

    # Rate Limiting & Throttling
    rate_limit_enabled: bool = True
    rate_limit_per_minute: int = 60
    rate_limit_per_hour: int = 1000
    max_tokens_per_user_per_day: int = 100000
    cost_alert_threshold_usd: float = 1000.0

    # Monitoring & Alerts
    sentry_dsn: str = ""
    sentry_traces_sample_rate: float = 0.1
    sentry_environment: str = "development"

    health_check_enabled: bool = True
    health_check_path: str = "/health"
    health_check_interval_seconds: int = 30

    # PII & Security
    pii_anonymization_enabled: bool = True
    pii_redaction_placeholder: str = "[REDACTED]"
    pii_min_confidence_score: float = 0.6
    pii_default_strategy: str = "replace"  # redact, replace, mask, hash, keep

    # Data Retention & GDPR
    retention_enabled: bool = True
    retention_chat_messages_days: int = 365  # 1 year
    retention_admin_uploads_days: int = 730  # 2 years
    retention_audit_logs_days: int = 2555  # 7 years (compliance)
    retention_auto_delete_enabled: bool = False  # Manual approval required by default

    # Feature Flags
    feature_admin_portal: bool = True
    feature_embeddable_widget: bool = True
    feature_telegram_integration: bool = True
    feature_slack_integration: bool = True
    feature_whatsapp_integration: bool = True
    feature_historical_ingestion: bool = True
    feature_document_upload: bool = True

    # Testing & Development
    test_mode: bool = False
    mock_external_apis: bool = False
    enable_api_docs: bool = True
    enable_reload: bool = True
    enable_profiling: bool = False

    @field_validator("secret_key")
    @classmethod
    def validate_secret_key(cls, v: str) -> str:
        """Ensure secret key is strong enough."""
        if len(v) < 32:
            raise ValueError("SECRET_KEY must be at least 32 characters long")
        return v

    @field_validator("agent_confidence_threshold")
    @classmethod
    def validate_confidence_threshold(cls, v: float) -> float:
        """Ensure confidence threshold is between 0 and 1."""
        if not 0 <= v <= 1:
            raise ValueError("agent_confidence_threshold must be between 0 and 1")
        return v

    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.environment == "production"

    @property
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.environment == "development"

    @property
    def is_uat(self) -> bool:
        """Check if running in UAT environment."""
        return self.environment == "uat"


# Global settings instance
settings = Settings()
