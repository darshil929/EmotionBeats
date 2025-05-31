"""
Socket.io middleware for logging, rate limiting, and error handling.

Provides middleware functions for connection monitoring, request rate limiting,
error handling, and performance tracking for Socket.io events.
"""

import os
import time
import logging
from typing import Dict, Any, Callable
from functools import wraps
from collections import defaultdict, deque

from app.core.redis import get_redis_cache
from app.utils.datetime_helper import utc_now

logger = logging.getLogger(__name__)

# Rate limiting configuration from environment
RATE_LIMIT_REQUESTS = int(os.getenv("SOCKETIO_RATE_LIMIT_REQUESTS", "100"))
RATE_LIMIT_WINDOW = int(os.getenv("SOCKETIO_RATE_LIMIT_WINDOW", "60"))  # seconds
RATE_LIMIT_ENABLED = os.getenv("SOCKETIO_RATE_LIMIT_ENABLED", "true").lower() == "true"

# In-memory rate limiting storage (fallback when Redis unavailable)
rate_limit_storage: Dict[str, deque] = defaultdict(deque)

# Performance metrics tracking
performance_metrics: Dict[str, Dict[str, Any]] = defaultdict(
    lambda: {
        "total_requests": 0,
        "total_duration": 0.0,
        "error_count": 0,
        "last_request": None,
    }
)


def connection_logger_middleware():
    """
    Creates middleware for logging Socket.io connection events.

    Tracks connection attempts, successful connections, and disconnections
    for monitoring and debugging purposes.
    """

    async def middleware(sid: str, environ: Dict[str, Any], next_handler: Callable):
        """
        Logs connection details and forwards to next handler.

        Captures client information and connection metadata for
        comprehensive connection monitoring.
        """
        try:
            # Extract client information
            client_ip = get_client_ip(environ)
            user_agent = environ.get("HTTP_USER_AGENT", "Unknown")
            connection_time = utc_now()

            logger.info(
                f"Socket.io connection attempt - SID: {sid}, IP: {client_ip}, "
                f"User-Agent: {user_agent[:100]}, Time: {connection_time}"
            )

            # Call next handler
            result = await next_handler(sid, environ)

            if result:
                logger.info(f"Socket.io connection successful - SID: {sid}")
            else:
                logger.warning(f"Socket.io connection rejected - SID: {sid}")

            return result

        except Exception as e:
            logger.error(f"Error in connection logger middleware for {sid}: {e}")
            return False

    return middleware


def rate_limiting_middleware(event_name: str):
    """
    Creates rate limiting middleware for specific Socket.io events.

    Prevents abuse by limiting the number of requests per client
    within a specified time window.
    """

    def decorator(handler: Callable) -> Callable:
        @wraps(handler)
        async def wrapper(sid: str, *args, **kwargs):
            """
            Applies rate limiting before executing the event handler.

            Tracks request frequency and blocks excessive requests
            from individual clients.
            """
            if not RATE_LIMIT_ENABLED:
                return await handler(sid, *args, **kwargs)

            try:
                # Check rate limit
                is_allowed = await check_rate_limit(sid, event_name)

                if not is_allowed:
                    logger.warning(
                        f"Rate limit exceeded for {sid} on event {event_name}"
                    )

                    # Send rate limit error to client
                    from app.services.socketio.server import get_socketio_server

                    sio = get_socketio_server()
                    if sio:
                        await sio.emit(
                            "rate_limit_error",
                            {
                                "error": "Rate limit exceeded",
                                "event": event_name,
                                "retry_after": RATE_LIMIT_WINDOW,
                            },
                            room=sid,
                        )

                    return

                # Execute handler if rate limit passed
                return await handler(sid, *args, **kwargs)

            except Exception as e:
                logger.error(f"Error in rate limiting middleware for {event_name}: {e}")
                # Continue execution on middleware error
                return await handler(sid, *args, **kwargs)

        return wrapper

    return decorator


def error_handling_middleware(event_name: str):
    """
    Creates error handling middleware for Socket.io event handlers.

    Provides centralized error handling, logging, and client notification
    for all Socket.io events.
    """

    def decorator(handler: Callable) -> Callable:
        @wraps(handler)
        async def wrapper(sid: str, *args, **kwargs):
            """
            Wraps event handlers with comprehensive error handling.

            Catches exceptions, logs errors, and sends appropriate
            error responses to clients.
            """
            start_time = time.time()

            try:
                # Execute the event handler
                result = await handler(sid, *args, **kwargs)

                # Track successful execution
                execution_time = time.time() - start_time
                await track_performance_metrics(event_name, execution_time, False)

                logger.debug(
                    f"Event {event_name} completed for {sid} in {execution_time:.3f}s"
                )
                return result

            except Exception as e:
                # Track error
                execution_time = time.time() - start_time
                await track_performance_metrics(event_name, execution_time, True)

                logger.error(
                    f"Error in event handler {event_name} for {sid}: {e}", exc_info=True
                )

                # Send generic error to client
                from app.services.socketio.server import get_socketio_server

                sio = get_socketio_server()
                if sio:
                    await sio.emit(
                        "server_error",
                        {
                            "error": "Internal server error",
                            "event": event_name,
                            "timestamp": utc_now().isoformat(),
                        },
                        room=sid,
                    )

                # Re-raise for upstream handling if needed
                raise

        return wrapper

    return decorator


def request_response_logger_middleware(event_name: str):
    """
    Creates middleware for logging Socket.io request and response data.

    Captures event data for debugging and monitoring purposes
    while filtering sensitive information.
    """

    def decorator(handler: Callable) -> Callable:
        @wraps(handler)
        async def wrapper(sid: str, *args, **kwargs):
            """
            Logs request data and response information for debugging.

            Filters sensitive data and tracks event flow for
            troubleshooting and optimization.
            """
            try:
                # Log request
                filtered_args = filter_sensitive_data(args)
                logger.debug(
                    f"Socket.io event {event_name} - SID: {sid}, "
                    f"Args: {filtered_args[:500]}..."  # Limit log size
                )

                # Execute handler
                result = await handler(sid, *args, **kwargs)

                # Log successful completion
                logger.debug(
                    f"Socket.io event {event_name} completed successfully for {sid}"
                )

                return result

            except Exception as e:
                logger.debug(f"Socket.io event {event_name} failed for {sid}: {str(e)}")
                raise

        return wrapper

    return decorator


async def check_rate_limit(sid: str, event_name: str) -> bool:
    """
    Checks if a client has exceeded the rate limit for an event.

    Uses Redis for distributed rate limiting with fallback to
    in-memory storage for high availability.
    """
    try:
        rate_key = f"rate_limit:{sid}:{event_name}"
        current_time = time.time()
        window_start = current_time - RATE_LIMIT_WINDOW

        # Try Redis first
        try:
            redis_client = await get_redis_cache()

            # Remove old entries
            await redis_client.zremrangebyscore(rate_key, 0, window_start)

            # Count current requests in window
            request_count = await redis_client.zcard(rate_key)

            if request_count >= RATE_LIMIT_REQUESTS:
                return False

            # Add current request
            await redis_client.zadd(rate_key, {str(current_time): current_time})
            await redis_client.expire(rate_key, RATE_LIMIT_WINDOW)

            return True

        except Exception as redis_error:
            logger.warning(f"Redis rate limiting failed, using fallback: {redis_error}")

            # Fallback to in-memory rate limiting
            return check_rate_limit_memory(sid, event_name, current_time, window_start)

    except Exception as e:
        logger.error(f"Error checking rate limit: {e}")
        # Allow request on error to avoid blocking legitimate traffic
        return True


def check_rate_limit_memory(
    sid: str, event_name: str, current_time: float, window_start: float
) -> bool:
    """
    Fallback in-memory rate limiting when Redis is unavailable.

    Provides basic rate limiting functionality using local memory
    for continued protection during Redis outages.
    """
    try:
        rate_key = f"{sid}:{event_name}"
        request_times = rate_limit_storage[rate_key]

        # Remove old requests outside window
        while request_times and request_times[0] < window_start:
            request_times.popleft()

        # Check if limit exceeded
        if len(request_times) >= RATE_LIMIT_REQUESTS:
            return False

        # Add current request
        request_times.append(current_time)

        return True

    except Exception as e:
        logger.error(f"Error in memory rate limiting: {e}")
        return True


async def track_performance_metrics(
    event_name: str, execution_time: float, is_error: bool
) -> None:
    """
    Tracks performance metrics for Socket.io events.

    Collects timing and error statistics for monitoring
    and performance optimization.
    """
    try:
        metrics = performance_metrics[event_name]

        metrics["total_requests"] += 1
        metrics["total_duration"] += execution_time
        metrics["last_request"] = utc_now().isoformat()

        if is_error:
            metrics["error_count"] += 1

        # Log slow operations
        if execution_time > 1.0:  # Log operations taking more than 1 second
            logger.warning(
                f"Slow Socket.io operation - Event: {event_name}, "
                f"Duration: {execution_time:.3f}s"
            )

    except Exception as e:
        logger.error(f"Error tracking performance metrics: {e}")


def get_client_ip(environ: Dict[str, Any]) -> str:
    """
    Extracts client IP address from Socket.io connection environment.

    Handles various proxy configurations and forwarded headers
    to determine the actual client IP address.
    """
    try:
        # Check for forwarded IP headers (proxy/load balancer)
        forwarded_for = environ.get("HTTP_X_FORWARDED_FOR")
        if forwarded_for:
            # Get first IP in case of multiple proxies
            return forwarded_for.split(",")[0].strip()

        # Check other common forwarded headers
        real_ip = environ.get("HTTP_X_REAL_IP")
        if real_ip:
            return real_ip.strip()

        # Fall back to remote address
        return environ.get("REMOTE_ADDR", "unknown")

    except Exception as e:
        logger.error(f"Error extracting client IP: {e}")
        return "unknown"


def filter_sensitive_data(data: Any) -> Any:
    """
    Filters sensitive information from logging data.

    Removes or masks sensitive fields like tokens, passwords,
    and personal information before logging.
    """
    try:
        if isinstance(data, dict):
            filtered = {}
            for key, value in data.items():
                if key.lower() in ["token", "password", "secret", "key", "auth"]:
                    filtered[key] = "***masked***"
                elif isinstance(value, (dict, list)):
                    filtered[key] = filter_sensitive_data(value)
                else:
                    filtered[key] = value
            return filtered

        elif isinstance(data, list):
            return [filter_sensitive_data(item) for item in data]

        elif isinstance(data, tuple):
            return tuple(filter_sensitive_data(list(data)))

        else:
            return data

    except Exception as e:
        logger.error(f"Error filtering sensitive data: {e}")
        return "***filter_error***"


async def get_performance_statistics() -> Dict[str, Any]:
    """
    Returns current performance statistics for all Socket.io events.

    Provides monitoring data for performance analysis and
    system health assessment.
    """
    try:
        stats = {}

        for event_name, metrics in performance_metrics.items():
            if metrics["total_requests"] > 0:
                avg_duration = metrics["total_duration"] / metrics["total_requests"]
                error_rate = (metrics["error_count"] / metrics["total_requests"]) * 100

                stats[event_name] = {
                    "total_requests": metrics["total_requests"],
                    "average_duration": round(avg_duration, 3),
                    "error_count": metrics["error_count"],
                    "error_rate": round(error_rate, 2),
                    "last_request": metrics["last_request"],
                }

        return stats

    except Exception as e:
        logger.error(f"Error getting performance statistics: {e}")
        return {}
