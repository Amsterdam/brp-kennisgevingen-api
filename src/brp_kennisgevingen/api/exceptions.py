from rest_framework import exceptions, status

CLASS_BY_CODE = {e.status_code: e for e in (exceptions.ParseError, exceptions.NotFound)}


class ProblemJsonException(exceptions.APIException):
    """API exception that dictates exactly
    how the application/problem+json response looks like.
    """

    status_code = status.HTTP_400_BAD_REQUEST

    def __init__(self, title, detail, status, invalid_params=None):
        code = CLASS_BY_CODE[status].default_code
        super().__init__(detail, code)
        self.code = code or self.default_code
        self.title = title
        self.status_code = status
        self.invalid_params = invalid_params


def raise_serializer_validation_error(serializer):
    invalid_params = []
    for field_name, err in serializer.errors.items():
        invalid_params.append({"name": field_name, "code": "date", "reason": str(err[0])})

    raise ProblemJsonException(
        title="Geen correcte waarde opgegeven.",
        detail="The request could not be understood by the server due to malformed syntax. "
        "The client SHOULD NOT repeat the request without modification.",
        status=status.HTTP_400_BAD_REQUEST,
        invalid_params=invalid_params,
    )
