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
    video = "video"
    story = "story"
    other = "other"


class ContentStatus(str, enum.Enum):
    draft = "draft"
    review = "review"
    approved = "approved"
    published = "published"
    archived = "archived"


class Platform(str, enum.Enum):
    telegram = "telegram"
    facebook = "facebook"
    instagram = "instagram"
    vk = "vk"
    website = "website"
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
