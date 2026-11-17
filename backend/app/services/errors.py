class ServiceError(Exception):
    """A request the rules do not allow; the message is shown to the user."""

    status_code = 400


class NotFound(ServiceError):
    status_code = 404


class Conflict(ServiceError):
    status_code = 409
