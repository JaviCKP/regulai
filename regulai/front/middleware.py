import traceback
import json
from .models import AuditLog


class ContentSecurityPolicyMiddleware:
    """Measure CSP compatibility while the existing UI still uses inline code."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response['Content-Security-Policy-Report-Only'] = (
            "default-src 'self'; script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
            "font-src 'self' data:; connect-src 'self'; object-src 'none'; "
            "base-uri 'self'; form-action 'self'; frame-ancestors 'self'"
        )
        return response


class ExceptionAuditMiddleware:
    """
    Middleware that logs unhandled Django exceptions to the AuditLog
    with action='System'.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        return response

    def process_exception(self, request, exception):
        """Log unhandled exceptions to AuditLog with action='System'."""
        try:
            user = request.user if hasattr(request, 'user') and request.user.is_authenticated else None
            tb = traceback.format_exc()

            details = json.dumps({
                'exception_type': type(exception).__name__,
                'exception_message': str(exception),
                'path': request.get_full_path(),
                'method': request.method,
                'traceback': tb,
            }, ensure_ascii=False, default=str)

            AuditLog.objects.create(
                user=user,
                action='System',
                details=details,
            )
        except Exception:
            # Avoid recursive errors - if logging itself fails, silently pass
            pass

        # Return None to let Django's default exception handling continue
        return None
