from pathlib import Path

from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_GET


@require_GET
def manifest(request):
    return JsonResponse({'id': '/', 'name': 'Daymark', 'short_name': 'Daymark', 'start_url': '/',
        'scope': '/', 'display': 'standalone', 'background_color': '#f4f5fa', 'theme_color': '#202944',
        'icons': [{'src': f'/static/tasks/icons/icon-{size}.png', 'sizes': f'{size}x{size}', 'type': 'image/png', 'purpose': 'any'} for size in [192, 512]]},
        content_type='application/manifest+json')


@require_GET
def service_worker(request):
    source = Path(__file__).parent / 'static' / 'tasks' / 'service-worker.js'
    response = HttpResponse(source.read_text(), content_type='text/javascript')
    response['Service-Worker-Allowed'] = '/'
    return response
