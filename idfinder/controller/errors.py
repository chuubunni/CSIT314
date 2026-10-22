class ControllerError(Exception):
    """Base class for errors the boundary layer turns into HTTP responses."""


class ValidationError(ControllerError):
    """Bad input from the user (show it with flash())."""


class NotFoundError(ControllerError):
    """The requested record doesn't exist (HTTP 404)."""


class PermissionDenied(ControllerError):
    """The user doesn't own the record (HTTP 403)."""