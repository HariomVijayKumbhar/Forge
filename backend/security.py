import re
from typing import Any
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from slowapi import Limiter
from slowapi.util import get_remote_address

# Setup rate limiter keying by remote IP
limiter = Limiter(key_func=get_remote_address)


# --- Secret Redaction Filter ---
SECRET_PATTERNS = [
    # Anthropic API Keys (e.g. sk-ant-api03-...)
    re.compile(r"sk-ant-[a-zA-Z0-9_\-]{15,}", re.IGNORECASE),
    # OpenAI style keys
    re.compile(r"sk-[a-zA-Z0-9]{20,}", re.IGNORECASE),
    # Google / Gemini API Keys (AIzaSy...)
    re.compile(r"AIzaSy[a-zA-Z0-9_\-]{20,}", re.IGNORECASE),
    # GitHub Personal Access Tokens & Fine-Grained tokens
    re.compile(r"ghp_[a-zA-Z0-9]{20,}", re.IGNORECASE),
    re.compile(r"github_pat_[a-zA-Z0-9_]{30,}", re.IGNORECASE),
    re.compile(r"gho_[a-zA-Z0-9]{20,}", re.IGNORECASE),
    # Bearer tokens in headers or text
    re.compile(r"Bearer\s+[a-zA-Z0-9\-_.~+/]+=*", re.IGNORECASE),
    # Generic password / secret / key assignment patterns in strings
    re.compile(r'(password|secret|api_key|key|token|auth)\s*[:=]\s*["\']?([^"\'\s]{8,})["\']?', re.IGNORECASE),
]


def redact_secrets(text: Any) -> Any:
    """Recursively redacts sensitive API keys and tokens from strings, dicts, or lists."""
    if text is None:
        return None
    if isinstance(text, str):
        redacted = text
        for pattern in SECRET_PATTERNS:
            if pattern.groups > 0:
                def repl(match: re.Match) -> str:
                    prefix = match.group(1)
                    return f'{prefix}="[REDACTED]"'
                redacted = pattern.sub(repl, redacted)
            else:
                redacted = pattern.sub("[REDACTED]", redacted)
        return redacted
    elif isinstance(text, dict):
        return {k: redact_secrets(v) for k, v in text.items()}
    elif isinstance(text, list):
        return [redact_secrets(item) for item in text]
    return text


# --- Security Headers Middleware ---
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)

        # CSP: Restrict resource loading
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: https:; "
            "font-src 'self' data: https:; "
            "connect-src 'self'"
        )

        # Prevent MIME type sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"

        # Prevent clickjacking
        response.headers["X-Frame-Options"] = "DENY"

        # Referrer Policy
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # HSTS (Strict Transport Security for 1 year)
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

        # XSS Protection filter
        response.headers["X-XSS-Protection"] = "1; mode=block"

        return response

