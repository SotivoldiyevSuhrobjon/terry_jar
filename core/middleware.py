from django.shortcuts import redirect
from django.urls import reverse


class ForcePasswordChangeMiddleware:
    """Admin bergan vaqtinchalik parol bilan kirgan xodim avval o'z parolini qo'yadi."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        u = getattr(request, "user", None)
        if u and u.is_authenticated and u.must_change_password:
            allowed = (reverse("password_change"), reverse("logout"), "/static/", "/healthz")
            if not request.path.startswith(allowed):
                if request.path.startswith("/api/"):
                    from django.http import JsonResponse
                    return JsonResponse({"error": "password_change"}, status=403)
                return redirect("password_change")
        return self.get_response(request)
