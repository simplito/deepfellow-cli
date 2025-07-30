"""Common validations."""

from .echo import echo


def validate_system() -> None:
    """Validate if the system has all dependencies."""
    # TODO Validate for Python verdion
    echo.debug("Implement Python version validation.")
    # TODO Validate for uv
    echo.debug("Implement uv existence validation.")
    # TODO Validate for poetry (infra)
    echo.debug("Implement (?) poetry existance validation.")
