"""
Redis connection configuration and management for Socket.io and caching services.
"""

import os
from typing import Optional
import redis.asyncio as redis
import logging

logger = logging.getLogger(__name__)

# Redis connection URLs from environment
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
SOCKETIO_REDIS_URL = os.getenv("SOCKETIO_REDIS_URL", "redis://redis:6379/1")

# Global Redis connection instances
_redis_cache: Optional[redis.Redis] = None
_redis_socketio: Optional[redis.Redis] = None


async def get_redis_cache() -> redis.Redis:
    """
    Returns the Redis connection instance for general caching operations.
    
    Creates a new connection pool if one doesn't exist.
    """
    global _redis_cache
    
    if _redis_cache is None:
        try:
            _redis_cache = redis.from_url(
                REDIS_URL,
                decode_responses=True,
                max_connections=20,
                retry_on_timeout=True
            )
            
            # Test the connection
            await _redis_cache.ping()
            logger.info("Redis cache connection established successfully")
            
        except Exception as e:
            logger.error(f"Failed to connect to Redis cache: {e}")
            raise
    
    return _redis_cache


async def get_redis_socketio() -> redis.Redis:
    """
    Returns the Redis connection instance for Socket.io session management.
    
    Uses a separate Redis database to avoid conflicts with cache data.
    """
    global _redis_socketio
    
    if _redis_socketio is None:
        try:
            _redis_socketio = redis.from_url(
                SOCKETIO_REDIS_URL,
                decode_responses=False,  # Socket.io requires binary mode
                max_connections=50,
                retry_on_timeout=True
            )
            
            # Test the connection
            await _redis_socketio.ping()
            logger.info("Redis Socket.io connection established successfully")
            
        except Exception as e:
            logger.error(f"Failed to connect to Redis Socket.io: {e}")
            raise
    
    return _redis_socketio


async def close_redis_connections():
    """
    Closes all Redis connections gracefully during application shutdown.
    """
    global _redis_cache, _redis_socketio
    
    if _redis_cache:
        await _redis_cache.close()
        _redis_cache = None
        logger.info("Redis cache connection closed")
    
    if _redis_socketio:
        await _redis_socketio.close()
        _redis_socketio = None
        logger.info("Redis Socket.io connection closed")


async def health_check_redis() -> dict:
    """
    Performs health checks on Redis connections.
    
    Returns status information for monitoring and debugging.
    """
    status = {
        "cache": {"status": "disconnected", "error": None},
        "socketio": {"status": "disconnected", "error": None}
    }
    
    try:
        cache_redis = await get_redis_cache()
        await cache_redis.ping()
        status["cache"]["status"] = "connected"
    except Exception as e:
        status["cache"]["error"] = str(e)
    
    try:
        socketio_redis = await get_redis_socketio()
        await socketio_redis.ping()
        status["socketio"]["status"] = "connected"
    except Exception as e:
        status["socketio"]["error"] = str(e)
    
    return status