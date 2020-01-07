"""{{ cookiecutter.title }}"""

import logging
import os

import click

logger = logging.getLogger("{{ cookiecutter.binary_name }}")


@click.group()
@click.option(
    "--log-level",
    type=click.Choice(["NOTSET", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]),
    default="INFO",
)
def cli(log_level: str) -> None:
    logger.setLevel(getattr(logging, log_level))


@cli.command()
@click.option("--name", help="Your name", default=lambda: os.environ.get("USER"))
def welcome(name: str) -> None:
    """Welcome!"""
    logger.info("Welcoming...")
    click.echo(f"Welcome! {name}")


if __name__ == "__main__":
    cli()
