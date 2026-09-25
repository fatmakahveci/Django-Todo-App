import ipaddress
import unicodedata
from datetime import datetime, timedelta, timezone as datetime_timezone

from django.conf import settings
from django.db.models import F
from django.http import HttpResponse
from django.utils import timezone
from django.utils.cache import add_never_cache_headers
from django.utils.crypto import salted_hmac
from django.utils.deprecation import MiddlewareMixin

from .models import AuthAttemptBucket


class AppSecurityMiddleware(MiddlewareMixin):
    def process_view(self, request, view_func, view_args, view_kwargs):
        name = request.resolver_match.view_name if request.resolver_match else None
        if request.method != "POST" or name not in {"login", "register", "admin:login"}:
            return None
        now = timezone.now()
        window = int(now.timestamp()) // 300
        expiry = datetime.fromtimestamp((window + 1) * 300, tz=datetime_timezone.utc)
        address = request.META.get("REMOTE_ADDR", "unknown")
        # Forwarded headers are trusted only from explicitly configured proxy addresses.
        try:
            peer = ipaddress.ip_address(address)
            trusted = any(peer in ipaddress.ip_network(network) for network in settings.AUTH_TRUSTED_PROXIES)
            if trusted:
                address = str(ipaddress.ip_address(request.META.get("HTTP_X_REAL_IP", address)))
        except ValueError:
            pass
        rules = [(f"ip:{address}", 40), (f"register:{address}", 5)] if name == "register" else [(f"ip:{address}", 40)]
        username = unicodedata.normalize("NFKC", request.POST.get("username", "")).casefold().strip()
        if username and name != "register":
            rules.append((f"account:{username}", 10))
        AuthAttemptBucket.objects.filter(expires_at__lte=now - timedelta(minutes=5)).delete()
        for identity, limit in rules:
            key = salted_hmac("auth-rate-limit", f"{window}:{identity}", algorithm="sha256").hexdigest()
            AuthAttemptBucket.objects.get_or_create(key=key, defaults={"expires_at": expiry})
            # Atomic increments share limits across all Gunicorn workers.
            AuthAttemptBucket.objects.filter(key=key).update(attempts=F("attempts") + 1)
            if AuthAttemptBucket.objects.get(key=key).attempts > limit:
                response = HttpResponse("Too many attempts. Please wait a few minutes and try again.", status=429, content_type="text/plain")
                response["Retry-After"] = str(max(1, int((expiry - now).total_seconds())))
                return response
        return None

    def process_response(self, request, response):
        # Dynamic pages and redirects may contain task data or authentication state.
        add_never_cache_headers(response)
        response.setdefault("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; font-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'")
        response.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        response.setdefault("Referrer-Policy", "same-origin")
        return response
