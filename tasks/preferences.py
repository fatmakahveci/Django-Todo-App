from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.utils import timezone, translation

from .models import UserPreferences


class PreferencesMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        profile = None
        if request.user.is_authenticated:
            profile = UserPreferences.objects.filter(user=request.user).first()
        language = profile.language if profile else request.COOKIES.get('django_language', 'en')
        if language not in {'en', 'tr'}:
            language = 'en'
        try:
            zone = ZoneInfo(profile.timezone) if profile else timezone.get_default_timezone()
        except ZoneInfoNotFoundError:
            zone = timezone.get_default_timezone()
        # Context managers restore thread-local state even when a view raises an error.
        with timezone.override(zone), translation.override(language):
            return self.get_response(request)
