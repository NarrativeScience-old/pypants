from typing import Dict

import click

from pypants.config import PROJECT_CONFIG
from pypants.generators.base import PythonPackageGenerator


class CLIPackageGenerator(PythonPackageGenerator):
    """Generator for a Python CLI package"""

    PACKAGE_TYPE = "cli"
    TOP_LEVEL_DIR = "packages"
    FOLDER_NAME_PREFIX = "cli_"

    @property
    def binary_name(self):
        """CLI binary name"""
        return f"example-{self.nickname}"

    @property
    def context(self) -> Dict:
        """Template context variables"""
        context = super().context
        context.update({"binary_name": self.binary_name, "platforms": "darwin,linux"})
        return context

    def print_extra_help(self) -> None:
        """Print extra help info to the terminal"""
        click.echo()
        click.secho("Try out your new CLI:", fg="green", bold=True)
        click.echo(
            f"{PROJECT_CONFIG.config_dir_path}/pants run {self.build_dir}:{self.binary_name} -- welcome"
        )
