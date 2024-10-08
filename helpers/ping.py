from django.http import JsonResponse


def ping_app(request):
    return JsonResponse({"message": "What's up?"})
