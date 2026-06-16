import re

# api/middleware/request_meta_middleware.py

VERSION_PATTERN = re.compile(r"^v(\d+)$")


def _extract_version_from_path(path):
    for segment in (p for p in path.split("/") if p):
        match = VERSION_PATTERN.match(segment)
        if match:
            return {
                "string": match.group(0),
                "number": int(match.group(1)),
            }
    return {"string": None, "number": None}


class RequestMetaMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.ip_address = (
            request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[0]
            or request.META.get("REMOTE_ADDR")
        )
        request.user_agent = request.META.get("HTTP_USER_AGENT", "")
        version_info = _extract_version_from_path(request.path)
        request.api_version = version_info["string"]
        request.api_version_number = version_info["number"]
        return self.get_response(request)
