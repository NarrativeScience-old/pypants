"""Contains functions for loading generator plugins"""
import importlib
import logging
import sys
from typing import Dict

from ..config import PROJECT_CONFIG  # noqa: I100
from .base import PackageGenerator  # noqa: I100

logger = logging.getLogger(__name__)


def load_project_generators() -> Dict[str, PackageGenerator]:
    """Load package generators defined in the project.

    Returns:
        dict of generator name (generator folder name) to package generator class

    """
    generators_path = PROJECT_CONFIG.config_dir_path.joinpath(".pypants/generators")
    generators = {}
    if generators_path.is_dir():
        sys.path.append(str(generators_path))
        for entry in generators_path.iterdir():
            if entry.is_dir():
                try:
                    mod = importlib.import_module(entry.name)
                    generators[entry.name] = mod.Generator
                except Exception as e:
                    logger.warning(
                        f"Failed to find a Generator class in {entry}: {str(e)}"
                    )

    return generators


# Create a singleton of package generator classes
PACKAGE_GENERATOR_MAP = load_project_generators()


def create_package_generator(
    package_type: str,
    nickname: str,
    title: str,
    description: str,
    top_level_dir: str = None,
    template: str = None,
) -> PackageGenerator:
    """Factory function for creating a package generator object.

    Args:
        package_type: Package type that corresponds to a key in the package generator map
        nickname: Nickname for the package. This will be used to folder names and
            other indentifiers.
        title: Title of the package
        description: Short description of the package
        top_level_dir: The top level directory is where the package will be stored.
            e.g. apps. Providing this during instantiation and not as a class
            attribute should only be done for dynamic generator classes.
        template: Template directory path to provide if you don't want it be
            inferred. Providing this during instantiation and not as a class
            attribute should only be done for dynamic generator classes.

    Returns:
        new package generator object

    """
    PackageGeneratorClass = PACKAGE_GENERATOR_MAP[package_type]
    generator = PackageGeneratorClass(
        nickname, title, description, top_level_dir=top_level_dir, template=template
    )
    return generator
