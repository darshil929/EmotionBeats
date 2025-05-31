"""
Socket.io service package initialization.

Provides centralized access to the Socket.io server instance and configuration.
"""

from app.services.socketio.server import sio, init_socketio, shutdown_socketio

__all__ = ["sio", "init_socketio", "shutdown_socketio"]