"""Security, CORS allowlisting, rate limiting, and boundary validation for R.I.O. public demo."""

from collections import defaultdict, deque
import os
import re
import secrets
import time
from typing import Deque, Dict, List, Optional, Tuple
from fastapi import HTTPException, Request, status


DEFAULT_DEV_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

# Patterns representing capabilities intentionally excluded from the public research sandbox
FORBIDDEN_INTENT_PATTERNS: List[Tuple[re.Pattern[str], str]] = [
    (
        re.compile(r"\b(rm\s+-rf|del\s+/f|mkfs|format\s+c:|shutdown|reboot|powershell|cmd\.exe|bash|sh\s+-c|subprocess|eval\(|exec\()\b", re.IGNORECASE),
        "Shell execution and OS system commands are disabled in the public research sandbox.",
    ),
    (
        re.compile(r"(/etc/passwd|/etc/shadow|[a-z]:\\|c:/users|~/|~/.ssh|\.env\b|local\s+(?:files?|folders?|directories|disk|drive)|filesystem|documents\s+folder|hard\s+drive)", re.IGNORECASE),
        "Host filesystem access is blocked; only the 3 synthetic sandbox documents can be read.",
    ),
    (
        re.compile(r"\b(whatsapp|telegram|send\s+email|smtp|webhook|curl\s+http|wget\s+http|exfiltrate|upload\s+to|post\s+to\s+external)\b", re.IGNORECASE),
        "External messaging, email delivery, and outbound network requests are disabled in the public demo.",
    ),
    (
        re.compile(r"\b(api[_\s-]?key|password|credential|token|secret|private\s+key|groq_api_key)\b", re.IGNORECASE),
        "Credential access and secret inspection are strictly prohibited.",
    ),
    (
        re.compile(r"\b(desktop\s+control|mouse\s+click|keyboard\s+type|android\s+device|adb\b|mcp\s+call|playwright|browser\s+automation)\b", re.IGNORECASE),
        "Local desktop, Android device, Playwright, and MCP tool integrations remain isolated to private local R.I.O. installations.",
    ),
]

THINK_TAG_RE = re.compile(r"<think>.*?</think>", re.IGNORECASE | re.DOTALL)
CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def get_app_env() -> str:
    return os.getenv("APP_ENV", "development").strip().lower()


def get_allowed_origins() -> List[str]:
    """Return strict CORS origin allowlist; wildcard '*' is rejected in production."""
    raw = os.getenv("DEMO_ALLOWED_ORIGINS", "").strip()
    env = get_app_env()

    if not raw:
        return [] if env == "production" else list(DEFAULT_DEV_ORIGINS)

    origins: List[str] = []
    for item in raw.split(","):
        origin = item.strip().rstrip("/")
        if not origin:
            continue
        if origin == "*":
            if env == "production":
                # Never allow wildcard CORS in production
                continue
            # Even in development, prefer explicit origins unless explicitly testing
            continue
        if origin.startswith("http://") or origin.startswith("https://"):
            origins.append(origin)

    if not origins and env != "production":
        return list(DEFAULT_DEV_ORIGINS)
    return origins


def get_session_ttl_seconds() -> int:
    try:
        ttl = int(os.getenv("SESSION_TTL_SECONDS", "1800"))
    except ValueError:
        ttl = 1800
    return max(1, min(ttl, 86400))


def get_step_delay_seconds() -> float:
    try:
        ms = int(os.getenv("DEMO_STEP_DELAY_MS", "850"))
    except ValueError:
        ms = 850
    ms = max(0, min(ms, 5000))
    return ms / 1000.0


def get_max_steps_per_session() -> int:
    return 6


def get_max_interactions_per_session() -> int:
    try:
        val = int(os.getenv("DEMO_MAX_INTERACTIONS", "25"))
    except ValueError:
        val = 25
    return max(5, min(val, 100))


def get_max_active_sessions() -> int:
    try:
        val = int(os.getenv("DEMO_MAX_ACTIVE_SESSIONS", "250"))
    except ValueError:
        val = 250
    return max(10, min(val, 2000))


def get_max_body_bytes() -> int:
    try:
        val = int(os.getenv("DEMO_MAX_BODY_BYTES", "16384"))
    except ValueError:
        val = 16384
    return max(1024, min(val, 65536))


def generate_session_id() -> str:
    """Generate a cryptographically random, unguessable session identifier."""
    return f"rio_{secrets.token_urlsafe(24)}"


def generate_short_id(prefix: str) -> str:
    return f"{prefix}_{secrets.token_hex(6)}"


def sanitize_text(text: str, max_len: int = 500) -> str:
    """Strip control characters and any private reasoning tags."""
    cleaned = THINK_TAG_RE.sub("", text or "")
    cleaned = CONTROL_CHARS_RE.sub("", cleaned)
    cleaned = " ".join(cleaned.strip().split())
    return cleaned[:max_len]


def detect_sandbox_boundary_trigger(task: str) -> Optional[str]:
    """Detect prompts requesting privileged local, shell, credential, or external network actions."""
    for pattern, reason in FORBIDDEN_INTENT_PATTERNS:
        if pattern.search(task):
            return reason
    return None


def get_client_ip(request: Request) -> str:
    # Prefer trusted edge proxy headers (Cloudflare / Render) when present to prevent XFF spoofing
    for edge_header in ("cf-connecting-ip", "true-client-ip"):
        edge_ip = request.headers.get(edge_header, "").strip()[:64]
        if edge_ip:
            return edge_ip
    forwarded_for = request.headers.get("x-forwarded-for", "")
    if forwarded_for:
        first_ip = forwarded_for.split(",")[0].strip()[:64]
        if first_ip:
            return first_ip
    if request.client and request.client.host:
        return request.client.host[:64]
    return "unknown"


class SlidingWindowRateLimiter:
    """Lightweight in-memory sliding-window throttler to protect free-tier resources."""

    def __init__(self) -> None:
        self._buckets: Dict[str, Deque[float]] = defaultdict(deque)
        self._last_prune: float = time.monotonic()

    def check(self, key: str, limit: int, window_seconds: int = 60) -> None:
        now = time.monotonic()
        cutoff = now - window_seconds
        bucket = self._buckets[key]

        while bucket and bucket[0] <= cutoff:
            bucket.popleft()

        if len(bucket) >= limit:
            retry_after = max(1, int(window_seconds - (now - bucket[0])) + 1)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded. Retry in {retry_after} seconds.",
                headers={"Retry-After": str(retry_after)},
            )

        bucket.append(now)

        # Periodically prune stale buckets to prevent unbounded memory growth
        if now - self._last_prune > 120:
            stale_keys = [
                k for k, dq in self._buckets.items() if not dq or dq[-1] <= cutoff
            ]
            for k in stale_keys:
                del self._buckets[k]
            self._last_prune = now

    def reset(self) -> None:
        self._buckets.clear()
        self._last_prune = time.monotonic()


def get_rate_limits() -> Dict[str, int]:
    def _read_int(name: str, default: int) -> int:
        try:
            return max(1, int(os.getenv(name, str(default))))
        except ValueError:
            return default

    return {
        "create_per_min": _read_int("DEMO_RATE_LIMIT_CREATE_PER_MIN", 15),
        "requests_per_min": _read_int("DEMO_RATE_LIMIT_REQ_PER_MIN", 180),
        "session_mutations_per_min": _read_int("DEMO_RATE_LIMIT_SESSION_MUTATIONS_PER_MIN", 30),
        "ip_mutations_per_min": _read_int("DEMO_RATE_LIMIT_IP_MUTATIONS_PER_MIN", 45),
    }


rate_limiter = SlidingWindowRateLimiter()
