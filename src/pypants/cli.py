"""Command line interface"""
import logging
import re

import click
from slugify import slugify

from .config import PROJECT_CONFIG
from .generators.load import create_package_generator, PACKAGE_GENERATOR_MAP
from .process_packages import PackageProcessor
from .requirements import update_third_party_import_map

logger = logging.getLogger(__name__)


@click.group()
@click.option(
    "--log-level",
    type=click.Choice(["NOTSET", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]),
    default="INFO",
)
def cli(log_level: str):
    """Base CLI command"""
    logging.basicConfig(level=getattr(logging, log_level.upper()))


@cli.command()
def process_packages() -> None:
    """Generate BUILD files"""
    processor = PackageProcessor()
    processor.register_packages()
    processor.ensure_no_circular_imports()
    processor.generate_build_files()
    logger.info("Done")


@cli.command()
@click.option("--target", help="Pants build target")
@click.option(
    "--include-3rdparty/--no-include-3rdparty",
    default=False,
    help="Include or exclude 3rdparty requirements in the list of dependencies",
)
def compute_package_dependencies(target: str, include_3rdparty: bool) -> None:
    """Compute a topologically-sorted list of dependencies for a given target"""
    processor = PackageProcessor()
    processor.register_packages()
    dependencies = processor.compute_package_dependencies(
        target, include_3rdparty=include_3rdparty
    )
    # Print each of the dependency's build directory paths to stdout so we can parse
    # the list with bash in a CI job
    for d in dependencies:
        print(d.build_dir)


@cli.command()
def process_requirements() -> None:
    """Update 3rdparty/python/import-map.json from requirements.txt"""
    update_third_party_import_map()


def _validate_package_nickname(
    ctx: click.Context, param: click.Parameter, value: str
) -> str:
    """Validate the package nickname and return a coerced form.

    This is meant to be passed to the ``callback`` argument of a ``@click.option()``
    decorator.

    Args:
        ctx: Click context object
        param: Click parameter object
        value: Value of the parameter, i.e. the nickname

    Returns:
        Coerced nickname

    """
    return slugify(
        re.sub(
            rf"^(?:{PROJECT_CONFIG.python_package_name_prefix}|cli_|python_)+(.*)$",
            r"\1",
            value,
        )
    )


@cli.command()
@click.option(
    "--type",
    "package_type",
    help="Package type",
    type=click.Choice(list(PACKAGE_GENERATOR_MAP.keys())),
    prompt=True,
)
@click.option(
    "--nickname",
    "nickname",
    callback=_validate_package_nickname,
    help="Package nickname",
    prompt="Enter a package nickname. This will be used to folder names and other"
    " identifiers. Examples: deploy | config_server ",
)
@click.option(
    "--title",
    help="Title of the package. Examples: Deploy CLI | Configuration Server",
    prompt="Enter a title for the package. We'll include this in the README."
    " Examples: Deploy CLI | Configuration Server ",
)
@click.option(
    "--description",
    help="Short description of the package",
    prompt="Enter a short description for the package. We'll include this in the"
    " README ",
)
def generate_package(
    package_type: str, nickname: str, title: str, description: str
) -> None:
    """Generate a new package folder"""
    generator = create_package_generator(package_type, nickname, title, description)
    generator.generate()
    generator.create_build_file()
    click.echo()
    click.secho("Your new package was successfully generated:", fg="green", bold=True)
    click.echo(generator.package_dir)
    generator.print_extra_help()


if __name__ == "__main__":
    cli()
