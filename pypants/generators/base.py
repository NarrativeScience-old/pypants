"""Contains the base class for a package generator"""
import inspect
import logging
import os
from pathlib import Path
import shutil
from typing import Dict, Optional

from cookiecutter.main import cookiecutter

from ..config import PROJECT_CONFIG
from ..process_packages import PackageProcessor

logger = logging.getLogger(__name__)


class PackageGenerator:
    """Base class for package generators.

    A package generator is responsible for creating a folder in the repo with standard
    boilerplate based on the type of package.
    """

    #: Package type must be defined in the child class
    PACKAGE_TYPE = None
    #: The top level directory is where the package will be stored. e.g. apps. It must
    #: be defined in the child class.
    TOP_LEVEL_DIR = None
    #: The folder containing the new package can have a prefix. This will depend on the
    #: package type.
    FOLDER_NAME_PREFIX = ""

    def __init__(
        self,
        nickname: str,
        title: str,
        description: str,
        top_level_dir: Optional[str] = None,
        template: Optional[str] = None,
    ) -> None:
        """

        Args:
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

        """
        self.nickname = nickname
        self.title = title
        self.description = description
        self._top_level_dir = top_level_dir or self.TOP_LEVEL_DIR
        # The new package will be created in this output folder
        self._output_dir = PROJECT_CONFIG.config_dir_path.joinpath(self._top_level_dir)
        # The generator template should be defined in a folder in the same directory as
        # the generator module. Alternatively, it can be provided explicitly.
        self._template = template or os.path.dirname(inspect.getfile(self.__class__))

    @property
    def folder_name(self) -> str:
        """Basename of the folder for the new package"""
        return self.FOLDER_NAME_PREFIX + self.nickname

    @property
    def package_dir(self) -> str:
        """Absolute path to the new package directory"""
        return os.path.join(
            os.environ["TALOS_ROOT"], self._top_level_dir, self.folder_name
        )

    @property
    def package_name(self) -> str:
        """Name of the package. This is usually the name used for importing."""
        return self.folder_name

    @property
    def build_dir(self) -> str:
        """Directory containing the package's BUILD file"""
        return os.path.join(self._top_level_dir, self.folder_name)

    @property
    def package_path(self) -> str:
        """Path to the package source code"""
        return os.path.join(self.package_dir, "src", self.package_name)

    @property
    def context(self) -> Dict:
        """Template context variables.

        Child classes can override this method and extend the dict.
        """
        return {
            "build_dir": self.build_dir,
            "description": self.description,
            "folder_name": self.folder_name,
            "package_name": self.package_name,
            "package_type": self.PACKAGE_TYPE,
            "title": self.title,
        }

    def generate(self) -> None:
        """Generate a new package in the repo"""
        try:
            cookiecutter(
                self._template,
                no_input=True,
                extra_context=self.context,
                replay=False,
                overwrite_if_exists=True,
                output_dir=self._output_dir,
            )
            self._post_generate()
        except Exception as e:
            logger.exception(f"Failed to generate the new package: {e}")
            shutil.rmtree(self.package_dir, ignore_errors=True)
            raise

    def _post_generate(self) -> None:
        """Optional post-generation step.

        This may be overridden by child classes.
        """
        pass

    def create_build_file(self) -> None:
        """Create the BUILD file"""
        processor = PackageProcessor()
        processor.register_packages()
        processor.generate_build_file(self.package_name)

    def print_extra_help(self) -> None:
        """Print extra help info to the terminal

        This may be overridden by child classes.
        """
        pass


class PythonPackageGenerator(PackageGenerator):
    """Generator for a generic Python package.

    This class is meant to be extended.
    """

    PACKAGE_TYPE = "python"

    @property
    def folder_name(self) -> str:
        """Basename of the folder for the new package"""
        return super().folder_name.replace("-", "_")

    @property
    def package_name(self) -> str:
        """Name of the package. This is usually the name used for importing."""
        return f"{PROJECT_CONFIG.python_package_name_prefix}{self.folder_name}"

    @property
    def build_dir(self) -> str:
        """Directory containing the package's BUILD file"""
        return os.path.join(super().build_dir, "src")

    def _post_generate(self) -> None:
        """Cleanup the generated package"""
        self._clean_init_files()

    def _clean_init_files(self) -> None:
        """For some reason a couple __init__.py files get generated. Remove them."""
        try:
            root = Path(self.package_dir)
            files = list(root.rglob("*.pyc"))
            files.append(root.joinpath("__init__.py"))
            files.append(root.joinpath("src/__init__.py"))
            for f in files:
                f.unlink()
        except Exception:
            pass
