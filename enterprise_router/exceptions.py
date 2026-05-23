class RouterError(Exception):
    """Base router error."""


class ValidationError(RouterError):
    """Invalid envelope, registration, or routing input."""


class AccessError(RouterError):
    """Authentication or authorization failure."""


class RegistrationError(RouterError):
    """Registration workflow error."""
