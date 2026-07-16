class AppException(Exception):
    status_code: int = 500
    error_code: str = "internal_error"

    def __init__(self, message: str, *, error_code: str | None = None) -> None:
        self.message = message
        if error_code is not None:
            self.error_code = error_code
        super().__init__(message)


class NotFoundError(AppException):
    status_code = 404
    error_code = "not_found"


class ConflictError(AppException):
    status_code = 409
    error_code = "conflict"


class ValidationError(AppException):
    status_code = 422
    error_code = "validation_error"


class UnauthorizedError(AppException):
    status_code = 401
    error_code = "unauthorized"


class ForbiddenError(AppException):
    status_code = 403
    error_code = "forbidden"
