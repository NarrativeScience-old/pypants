"""Contains PythonRequirement class"""
from ..config import PROJECT_CONFIG  # noqa: I100
from .base import BuildTarget  # noqa: I100

# Parent directory name containing 3rdparty requirements.txt
REQUIREMENTS_DIR = PROJECT_CONFIG.third_party_requirements_path.parent


class PythonRequirement(BuildTarget):
    """Represents a Python requirement build target in Pants"""

    def __init__(self, package_name: str) -> None:
        self.package_name = package_name
        self.key = f"{REQUIREMENTS_DIR}:{self.package_name}"
