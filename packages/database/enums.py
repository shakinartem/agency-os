"""Shared enumerations used across models."""

import enum


class UserRole(str, enum.Enum):
    admin = "admin"
    manager = "manager"
    viewer = "viewer"


class LeadStatus(str, enum.Enum):
    new = "new"
    contacted = "contacted"
    qualified = "qualified"
    converted = "converted"
    lost = "lost"


class LeadSource(str, enum.Enum):
    telegram = "telegram"
    whatsapp = "whatsapp"
    website = "website"
    referral = "referral"
    manual = "manual"
    other = "other"


class ConversationSource(str, enum.Enum):
    telegram = "telegram"
    whatsapp = "whatsapp"
    website = "website"
    api = "api"


class ConversationStatus(str, enum.Enum):
    active = "active"
    pending = "pending"
    closed = "closed"


class MessageRole(str, enum.Enum):
    user = "user"
    assistant = "assistant"
    system = "system"


class ContentType(str, enum.Enum):
    post = "post"
    article = "article"
    commercial_proposal = "commercial_proposal"
    rubric = "rubric"
    carousel = "carousel"
    video_script = "video_script"
    short_script = "short_script"
    story = "story"
    other = "other"


class ContentStatus(str, enum.Enum):
    draft = "draft"
    review = "review"
    approved = "approved"
    published = "published"
    archived = "archived"
    queued = "queued"
    planning = "planning"
    researching = "researching"
    drafting = "drafting"
    evaluating = "evaluating"
    revising = "revising"
    humanizing = "humanizing"
    adapting = "adapting"
    generating_media = "generating_media"
    media_review = "media_review"
    final_review = "final_review"
    ready = "ready"
    exporting = "exporting"
    exported = "exported"
    failed = "failed"


class GenerationRunStatus(str, enum.Enum):
    queued = "queued"
    running = "running"
    awaiting_review = "awaiting_review"
    ready = "ready"
    failed = "failed"
    cancelled = "cancelled"


class GenerationStepStatus(str, enum.Enum):
    queued = "queued"
    running = "running"
    passed = "passed"
    failed = "failed"
    skipped = "skipped"


class MediaStatus(str, enum.Enum):
    queued = "queued"
    generating = "generating"
    review = "review"
    ready = "ready"
    failed = "failed"


class ExportStatus(str, enum.Enum):
    queued = "queued"
    sending = "sending"
    accepted = "accepted"
    failed = "failed"


class Platform(str, enum.Enum):
    telegram = "telegram"
    vk = "vk"
    instagram = "instagram"
    facebook = "facebook"
    dzen = "dzen"
    website = "website"
    linkedin = "linkedin"
    other = "other"


class PublicationStatus(str, enum.Enum):
    scheduled = "scheduled"
    publishing = "publishing"
    published = "published"
    failed = "failed"


class IntegrationHealth(str, enum.Enum):
    healthy = "healthy"
    degraded = "degraded"
    down = "down"


class IntegrationAction(str, enum.Enum):
    sync = "sync"
    push = "push"
    pull = "pull"
    test = "test"
    other = "other"


class IntegrationActionStatus(str, enum.Enum):
    success = "success"
    failed = "failed"
    pending = "pending"
