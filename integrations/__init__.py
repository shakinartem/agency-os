"""Mock integration adapters for Agency OS."""

from .base import BaseIntegration
from .crm import CRMIntegration
from .consultation import ConsultationIntegration
from .content import ContentFarmIntegration
from .autoposter import AutoposterIntegration
from .reports import ReportsIntegration

__all__ = [
    "BaseIntegration",
    "CRMIntegration",
    "ConsultationIntegration",
    "ContentFarmIntegration",
    "AutoposterIntegration",
    "ReportsIntegration",
]
