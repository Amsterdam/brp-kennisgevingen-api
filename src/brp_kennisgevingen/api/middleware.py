from django.conf import settings


class APIVersionMiddleware:
    """
    Simple middleware to add the API version to each response. Needed to adhere to the
    API Design rules linter.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response["API-Version"] = settings.SPECTACULAR_SETTINGS["VERSION"]
        return response
