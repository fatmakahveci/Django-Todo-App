from django.shortcuts import render


def server_error(request):
    return render(request, 'tasks/server_error.html', {'error_id': getattr(request, 'error_id', '')}, status=500)
