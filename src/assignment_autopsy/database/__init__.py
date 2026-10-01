"""
assignment_autopsy.database
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Database engine and session management package.

:copyright: (c) 2026-present DA-344 (aka Developer Anonymous)
:license: MIT, see LICENSE for more details
"""

from .session import get_session

__all__ = ["get_session"]
