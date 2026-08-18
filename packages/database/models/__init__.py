"""SQLAlchemy ORM models — import all to ensure metadata registration."""

from sqlalchemy import event

from .user import User
from .project import Project
from .lead import Lead
from .lead_event import LeadEvent
from .conversation import Conversation
from .conversation_message import ConversationMessage
from .content_item import ContentItem
from .content_plan import ContentPlan
from .publication import Publication
from .report_snapshot import ReportSnapshot
from .integration_config import IntegrationConfig
from .integration_log import IntegrationLog
from .system_setting import SystemSetting
from .content_factory import (
    BrandProfile,
    Rubric,
    GenerationRun,
    GenerationStep,
    ContentVersion,
    ContentVariant,
    Evaluation,
    MediaAsset,
    ExportDelivery,
    ProductionBatch,
    ProductionBatchItem,
    ReviewDecision,
    PerformanceSnapshot,
    TaskOutbox,
)
from .knowledge import KnowledgeDocument, KnowledgeChunk
from .model_router_snapshot import ModelRouterSnapshot


def _strip_internal_provider_meta(value):
    """Keep provider telemetry in GenerationStep traces, never in authored content JSON."""
    if isinstance(value, dict):
        return {
            key: _strip_internal_provider_meta(child)
            for key, child in value.items()
            if key != "_provider_meta"
        }
    if isinstance(value, list):
        return [_strip_internal_provider_meta(child) for child in value]
    return value


def _sanitize_content_json(_target, value, _oldvalue, _initiator):
    return _strip_internal_provider_meta(value)


event.listen(ContentItem.structured_json, "set", _sanitize_content_json, retval=True)
event.listen(ContentVersion.structured_json, "set", _sanitize_content_json, retval=True)


__all__ = [
    "User", "Project", "Lead", "LeadEvent", "Conversation", "ConversationMessage",
    "ContentItem", "ContentPlan", "Publication", "ReportSnapshot", "IntegrationConfig",
    "IntegrationLog", "SystemSetting", "BrandProfile", "Rubric", "GenerationRun",
    "GenerationStep", "ContentVersion", "ContentVariant", "Evaluation", "MediaAsset",
    "ExportDelivery", "ProductionBatch", "ProductionBatchItem", "ReviewDecision",
    "PerformanceSnapshot", "TaskOutbox", "KnowledgeDocument", "KnowledgeChunk",
    "ModelRouterSnapshot",
]
