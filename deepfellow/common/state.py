# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""CLI runtime state."""

from dataclasses import MISSING, dataclass, field, fields
from pathlib import Path
from typing import Any, ClassVar

from deepfellow.common.defaults import DF_CLI_CONFIG_PATH, DF_CLI_SECRETS_PATH


class SingletonMeta(type):
    """Metaclass enforcing a single instance per class.

    Calling the class always returns the same instance, so an accidental
    second ``AppState()`` anywhere reuses the live state instead of creating
    a divergent copy.
    """

    _instances: ClassVar[dict[type, Any]] = {}

    def __call__(cls, *args: Any, **kwargs: Any) -> Any:
        """Return the existing instance, creating it only on first call."""
        if cls not in cls._instances:
            cls._instances[cls] = super().__call__(*args, **kwargs)

        return cls._instances[cls]


@dataclass
class AppState(metaclass=SingletonMeta):
    """Singleton holding CLI-wide runtime flags populated once by the main() callback.

    Constructing ``AppState()`` returns the shared instance with its current (possibly
    mutated) values — it does not reset fields. Use ``reset()`` to restore defaults.
    """

    debug: bool = False
    yes: bool = False
    non_interactive: bool = False
    cli_config: dict[str, Any] = field(default_factory=dict)
    cli_config_file: Path = DF_CLI_CONFIG_PATH
    cli_secrets_file: Path = DF_CLI_SECRETS_PATH

    def reset(self) -> None:
        """Restore every field to its default. Intended for test isolation."""
        for f in fields(self):
            default = f.default_factory() if f.default_factory is not MISSING else f.default
            setattr(self, f.name, default)


state = AppState()
