from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler


def origin(url):
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username is not None or parsed.password is not None:
        raise ValueError("expected an HTTP origin without user information")
    port = parsed.port if parsed.port is not None else (443 if parsed.scheme == "https" else 80)
    return parsed.scheme, parsed.hostname.lower(), port


class CredentialRedirects(HTTPRedirectHandler):
    """Install only on an owner-classified credentialed client's transport."""

    def __init__(self, *, allow_same_origin_reads=False):
        self.allow_same_origin_reads = allow_same_origin_reads

    def redirect_request(self, request, response, code, message, headers, new_url):
        if not self.allow_same_origin_reads or request.get_method() not in {"GET", "HEAD"}:
            return None
        try:
            if origin(request.full_url) != origin(new_url):
                return None
        except ValueError:
            return None
        return super().redirect_request(request, response, code, message, headers, new_url)
