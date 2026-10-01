"""
assignment_autopsy.database.models
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Database SQLAlchemy models.

:copyright: (c) 2026-present DA-344 (aka Developer Anonymous)
:license: MIT, see LICENSE for more details.
"""

from .assignment import Assignment
from .base import Base
from .evaluation import Evaluation
from .file_asset import FileAsset
from .file_asset_view import FileAssetView
from .group import Group
from .membership import Membership
from .rubric import CriterionLevelDescription, Rubric, RubricCriterion, RubricLevel
from .session import Session
from .submission import Submission
from .user import User

__all__ = [
    "Assignment",
    "Base",
    "CriterionLevelDescription",
    "Evaluation",
    "FileAsset",
    "FileAssetView",
    "Group",
    "Membership",
    "Rubric",
    "RubricCriterion",
    "RubricLevel",
    "Session",
    "Submission",
    "User",
]
