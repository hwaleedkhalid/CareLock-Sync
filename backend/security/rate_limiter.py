"""
CareLock Sync - Redis-Based Rate Limiting Implementation
Prevents brute force attacks and mass PHI exfiltration

Features:
- Per-user rate limiting
- Per-endpoint rate limiting
- Per-IP rate limiting
- Different limits for different sensitivity levels
- Automatic blocking and alerting
"""

from fastapi import Request, HTTPException
from typing import Optional, Callable
import redis
import time
import json
from datetime import datetime, timedelta
import hashlib

class RedisRateLimiter:
    """
    Production-grade rate limiter using Redis
    
    Tracks requests per:
    - User ID
    - IP address
    - Endpoint
    - Tenant ID
    """
    
    def __init__(self, redis_url: str = "redis://localhost:6379"):
        """
        Initialize rate limiter
        
        Args:
            redis_url: Redis connection URL
        """
        self.redis_client = redis.from_url(redis_url, decode_responses=True)
        
        # Rate limit configurations (requests per hour)
        self.limits = {
            # PHI access endpoints (very restrictive)
            'phi_read': {
                'limit': 100,
                'window': 3600,  # 1 hour
                'block_duration': 3600,  # Block for 1 hour
            },
            'phi_ssn': {
                'limit': 10,
                'window': 3600,
                'block_duration': 7200,  # Block for 2 hours
            },
            
            # Search endpoints (moderate)
            'search': {
                'limit': 200,
                'window': 3600,
                'block_duration': 1800,
            },
            
            # Authentication endpoints (strict)
            'login': {
                'limit': 5,
                'window': 300,  # 5 minutes
                'block_duration': 900,  # Block for 15 minutes
            },
            
            # General API endpoints
            'api_general': {
                'limit': 1000,
                'window': 3600,
                'block_duration': 600,
            },
            
            # Health check (permissive)
            'health': {
                'limit': 10000,
                'window': 3600,
                'block_duration': 0,
            }
        }
    
    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP from request"""
        # Check X-Forwarded-For header (if behind proxy)
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        
        # Check X-Real-IP header
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        
        # Fall back to client host
        return request.client.host if request.client else "unknown"
    
    def _get_rate_limit_key(
        self,
        identifier: str,
        endpoint_category: str,
        scope: str = "user"
    ) -> str:
        """
        Generate Redis key for rate limiting
        
        Args:
            identifier: User ID, IP address, etc.
            endpoint_category: Category of endpoint (phi_read, login, etc.)
            scope: Type of limit (user, ip, tenant)
        
        Returns:
            Redis key string
        """
        timestamp = int(time.time())
        window = self.limits[endpoint_category]['window']
        window_start = timestamp - (timestamp % window)
        
        return f"ratelimit:{scope}:{endpoint_category}:{identifier}:{window_start}"
    
    def _is_blocked(self, identifier: str, endpoint_category: str) -> bool:
        """Check if user/IP is currently blocked"""
        block_key = f"blocked:{endpoint_category}:{identifier}"
        return self.redis_client.exists(block_key) > 0
    
    def _block_user(self, identifier: str, endpoint_category: str):
        """Block user/IP for configured duration"""
        config = self.limits[endpoint_category]
        block_duration = config['block_duration']
        
        if block_duration > 0:
            block_key = f"blocked:{endpoint_category}:{identifier}"
            self.redis_client.setex(block_key, block_duration, "1")
            
            # Log the block
            self._log_block(identifier, endpoint_category, block_duration)
    
    def _log_block(self, identifier: str, endpoint_category: str, duration: int):
        """Log rate limit violation"""
        log_entry = {
            'timestamp': datetime.utcnow().isoformat(),
            'identifier': identifier,
            'category': endpoint_category,
            'duration': duration,
            'reason': 'rate_limit_exceeded'
        }
        
        # Store in Redis list (last 1000 violations)
        log_key = "ratelimit:violations"
        self.redis_client.lpush(log_key, json.dumps(log_entry))
        self.redis_client.ltrim(log_key, 0, 999)  # Keep only last 1000
        
        print(f"⚠️  RATE LIMIT VIOLATION: {identifier} blocked for {duration}s on {endpoint_category}")
    
    def check_rate_limit(
        self,
        request: Request,
        endpoint_category: str,
        user_id: Optional[str] = None,
        tenant_id: Optional[int] = None
    ) -> bool:
        """
        Check if request should be rate limited
        
        Args:
            request: FastAPI request object
            endpoint_category: Category of endpoint
            user_id: Optional user ID for user-based limiting
            tenant_id: Optional tenant ID for tenant-based limiting
        
        Returns:
            True if allowed, False if rate limited
        
        Raises:
            HTTPException: If rate limit exceeded
        """
        if endpoint_category not in self.limits:
            endpoint_category = 'api_general'
        
        config = self.limits[endpoint_category]
        ip_address = self._get_client_ip(request)
        
        # Check multiple scopes
        checks = []
        
        # 1. IP-based rate limit
        if ip_address:
            checks.append(('ip', ip_address))
        
        # 2. User-based rate limit
        if user_id:
            checks.append(('user', user_id))
        
        # 3. Tenant-based rate limit (prevents tenant-wide abuse)
        if tenant_id:
            checks.append(('tenant', str(tenant_id)))
        
        for scope, identifier in checks:
            # Check if already blocked
            if self._is_blocked(identifier, endpoint_category):
                raise HTTPException(
                    status_code=429,
                    detail=f"Too many requests. You are temporarily blocked. Try again later.",
                    headers={"Retry-After": "3600"}
                )
            
            # Get current count
            key = self._get_rate_limit_key(identifier, endpoint_category, scope)
            current_count = self.redis_client.get(key)
            
            if current_count is None:
                current_count = 0
            else:
                current_count = int(current_count)
            
            # Check limit
            if current_count >= config['limit']:
                # Block the user/IP
                self._block_user(identifier, endpoint_category)
                
                raise HTTPException(
                    status_code=429,
                    detail=f"Rate limit exceeded. Maximum {config['limit']} requests per {config['window']}s.",
                    headers={
                        "Retry-After": str(config['block_duration']),
                        "X-RateLimit-Limit": str(config['limit']),
                        "X-RateLimit-Remaining": "0",
                        "X-RateLimit-Reset": str(int(time.time()) + config['window'])
                    }
                )
            
            # Increment counter
            pipe = self.redis_client.pipeline()
            pipe.incr(key)
            pipe.expire(key, config['window'])
            pipe.execute()
        
        return True
    
    def get_remaining_requests(
        self,
        identifier: str,
        endpoint_category: str,
        scope: str = "user"
    ) -> dict:
        """
        Get rate limit status for identifier
        
        Returns:
            Dict with limit, used, remaining, reset_time
        """
        if endpoint_category not in self.limits:
            endpoint_category = 'api_general'
        
        config = self.limits[endpoint_category]
        key = self._get_rate_limit_key(identifier, endpoint_category, scope)
        
        current_count = self.redis_client.get(key)
        current_count = int(current_count) if current_count else 0
        
        ttl = self.redis_client.ttl(key)
        reset_time = int(time.time()) + ttl if ttl > 0 else int(time.time()) + config['window']
        
        return {
            'limit': config['limit'],
            'used': current_count,
            'remaining': max(0, config['limit'] - current_count),
            'reset_time': reset_time,
            'window': config['window']
        }
    
    def get_violation_log(self, limit: int = 100) -> list:
        """Get recent rate limit violations"""
        log_key = "ratelimit:violations"
        violations = self.redis_client.lrange(log_key, 0, limit - 1)
        return [json.loads(v) for v in violations]
    
    def clear_user_limits(self, user_id: str):
        """Clear all rate limits for a user (admin function)"""
        # Find all keys for this user
        pattern = f"ratelimit:user:*:{user_id}:*"
        keys = self.redis_client.keys(pattern)
        
        if keys:
            self.redis_client.delete(*keys)
        
        # Also clear blocks
        for category in self.limits.keys():
            block_key = f"blocked:{category}:{user_id}"
            self.redis_client.delete(block_key)
        
        print(f"✅ Cleared all rate limits for user: {user_id}")


# Dependency for FastAPI routes
def get_rate_limiter() -> RedisRateLimiter:
    """Get rate limiter instance"""
    return RedisRateLimiter()


# Decorator for easy use
def rate_limit(category: str):
    """
    Decorator to apply rate limiting to routes
    
    Usage:
        @app.get("/api/v1/patients/")
        @rate_limit("phi_read")
        async def get_patients():
            pass
    """
    def decorator(func: Callable):
        async def wrapper(request: Request, *args, **kwargs):
            limiter = get_rate_limiter()
            
            # Extract user info from request state (set by auth middleware)
            user_id = getattr(request.state, 'user_id', None)
            tenant_id = getattr(request.state, 'tenant_id', None)
            
            # Check rate limit
            limiter.check_rate_limit(
                request,
                category,
                user_id=user_id,
                tenant_id=tenant_id
            )
            
            # Call original function
            return await func(request, *args, **kwargs)
        
        return wrapper
    return decorator


# Test function
if __name__ == "__main__":
    print("="*70)
    print("Testing Redis Rate Limiter")
    print("="*70)
    
    # Initialize limiter
    limiter = RedisRateLimiter()
    
    # Simulate requests
    print("\nSimulating 15 login attempts from same IP...")
    
    from fastapi import Request
    from starlette.datastructures import Headers
    
    for i in range(15):
        # Create mock request
        headers = Headers({"host": "localhost"})
        request = Request(scope={
            "type": "http",
            "headers": headers.raw,
            "client": ("192.168.1.100", 8000),
            "path": "/api/v1/auth/login"
        })
        
        try:
            limiter.check_rate_limit(request, "login", user_id=f"user_{i}")
            print(f"  Request {i+1}: ✅ Allowed")
        except HTTPException as e:
            print(f"  Request {i+1}: ❌ Blocked - {e.detail}")
    
    print("\n" + "="*70)
    print("Rate limiting test complete!")
    print("="*70)
