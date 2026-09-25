"""Minimal error events: no URLs, task text, credentials, IPs, or traceback locals."""
import json
import logging
import time
import uuid
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler

from django.utils.deprecation import MiddlewareMixin


def event_for(record):
    request = getattr(record, 'request', None)
    error_id = getattr(request, 'error_id', None) or getattr(record, 'error_id', None)
    if not error_id:
        error_id = uuid.uuid4().hex
        record.error_id = error_id
    method = getattr(request, 'method', '')
    status = getattr(record, 'status_code', 500)
    return {'event': 'application_error', 'error_id': error_id,
            'status': status if isinstance(status, int) else 500,
            'method': method if method in {'GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'HEAD', 'OPTIONS'} else 'OTHER',
            'exception': record.exc_info[0].__name__ if record.exc_info and record.exc_info[0] else None}


class PrivateErrorFormatter(logging.Formatter):
    def format(self, record):
        return json.dumps(event_for(record))


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class ErrorWebhookHandler(logging.Handler):
    def __init__(self, endpoint=''):
        super().__init__(level=logging.ERROR)
        if endpoint and (urlsplit(endpoint).scheme != 'https' or not urlsplit(endpoint).hostname):
            raise ValueError('ERROR_WEBHOOK_URL must use HTTPS.')
        self.endpoint = endpoint
        self.last_sent = float('-inf')

    def emit(self, record):
        now = time.monotonic()
        if not self.endpoint or now - self.last_sent < 60:
            return
        self.last_sent = now
        try:
            payload = json.dumps(event_for(record)).encode()
            request = Request(self.endpoint, data=payload, headers={'Content-Type': 'application/json'}, method='POST')
            with build_opener(NoRedirect()).open(request, timeout=2) as response:
                response.read(1024)
        except Exception:
            # Monitoring outages must never replace the original application response.
            # The structured console event is still available when delivery fails.
            pass


class ErrorIdMiddleware(MiddlewareMixin):
    def process_exception(self, request, exception):
        request.error_id = uuid.uuid4().hex
        return None

    def process_response(self, request, response):
        if response.status_code >= 500:
            request.error_id = getattr(request, 'error_id', None) or uuid.uuid4().hex
            response['X-Error-ID'] = request.error_id
        return response
