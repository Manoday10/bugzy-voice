"""
CRM Module

This module handles customer relationship management functionality including:
- Session management
- User data persistence
"""

from app.services.crm.sessions import (
    _init_mongo_if_needed,
    load_sessions_from_file,
    save_session_to_file,
    load_user_session,
    delete_user_session,
)

__all__ = [
    '_init_mongo_if_needed',
    'load_sessions_from_file',
    'save_session_to_file',
    'load_user_session',
    'delete_user_session',
]