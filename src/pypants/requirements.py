"""Contains functions for working with requirements.txt"""

from copy import deepcopy
import glob
import json
import logging
import os
import subprocess
import sys
import tarfile
import tempfile
from typing import Dict, List, Tuple, TYPE_CHECKING
import zipfile

import pkg_resources

from .config import PROJECT_CONFIG
from .exceptions import (
    DistributionError,
    InvalidTopLevelFile,
    MissingDistributionMetadataFile,
    NoProjectName,
    UnsupportedDistributionFormat,
)

if TYPE_CHECKING:
    import io

logger = logging.getLogger(__name__)


# This file contains a map from the import name found in *.py to the library's project
# name (i.e. requirements.txt name)
try:
    with PROJECT_CONFIG.third_party_import_map_path.open() as f:
        THIRD_PARTY_IMPORT_MAP = json.load(f)
except FileNotFoundError:
    THIRD_PARTY_IMPORT_MAP = {}

# Top-level Python package distribution names to ignore when generating the third-party
# import map
IGNORE_TOP_LEVEL_IMPORTS = {"testing", "tests", "test"}


def _requirement_name(requirement: pkg_resources.Requirement) -> str:
    """Build a full requirement project name that includes extras"""
    name = requirement.name
    if len(requirement.extras) > 1:
        raise NotImplementedError(
            f"Multiple requirement extras are not supported: {requirement.extras}"
        )
    elif len(requirement.extras) == 1:
        name = f"{name}[{requirement.extras[0]}]"

    return name


def _parse_top_level_imports_from_file(
    distribution_path, f: "io.TextIOWrapper"
) -> List[str]:
    """Get the top-level import names from a top_level.txt file

    Args:
        distribution_path: Path to the .whl or .tar.gz file containing package metadata
        f: File handle

    Returns:
        Top-level import names for the distribution (case-sensitive).
        e.g. ``["auth0"]`` for a project name of ``auth0-python``.

    Raises:
        :py:exc:`.InvalidTopLevelFile` when no top level import names could be found

    """
    imports = [
        line
        for line in f.read().decode().split("\n")
        if len(line.strip()) > 0
        and line.strip() not in IGNORE_TOP_LEVEL_IMPORTS
        and not line.strip().startswith("_")
    ]
    if len(imports) == 0:
        raise InvalidTopLevelFile(
            f"No top-level imports found in distribution package for {distribution_path}"
        )

    return imports


def _get_project_name_from_metadata_file(
    distribution_path, f: "io.TextIOWrapper"
) -> str:
    """Get the project name from a METADATA or PKG-INFO file

    Args:
        distribution_path: Path to the .whl or .tar.gz file containing package metadata
        f: File handle

    Returns:
        Project name for the distribution (case-sensitive)

    Raises:
        :py:exc:`.NoProjectName` when no project name could be parsed from distribution
            metadata

    """
    for line in f.readlines():
        if line.decode().startswith("Name:"):
            project_name = line.decode().split(":")[1].strip()
            return project_name

    raise NoProjectName(f"No project name found in {distribution_path}")


def _get_package_names_from_wheel(distribution_path: str) -> Tuple[List[str], str]:
    """Get the top-level import name and project name for a given .whl distribution

    Args:
        distribution_path: Path to the .whl file containing package metadata

    Returns:
        Tuple of ``(top_level_imports, project_name)``

    Raises:
        :py:exc:`.MissingDistributionMetadataFile`

    """
    zf = zipfile.ZipFile(distribution_path)
    top_level_imports = None
    project_name = None
    for name in zf.namelist():
        if os.path.basename(name) == "top_level.txt":
            with zf.open(name) as f:
                top_level_imports = _parse_top_level_imports_from_file(
                    distribution_path, f
                )
        elif name.endswith(".dist-info/METADATA"):
            with zf.open(name) as f:
                project_name = _get_project_name_from_metadata_file(
                    distribution_path, f
                )

        if top_level_imports is not None and project_name is not None:
            break

    if project_name is None:
        raise MissingDistributionMetadataFile(
            f"Could not find METADATA in {distribution_path}"
        )
    elif top_level_imports is None:
        top_level_imports = [project_name]
        logger.debug(
            f"Could not find top_level.txt in {distribution_path}."
            f" Defaulting top level import list to {top_level_imports}"
        )

    return top_level_imports, project_name


def _get_package_names_from_tar(distribution_path: str) -> Tuple[List[str], str]:
    """Get the top-level import name and project name for a given .tar.gz distribution

    Args:
        distribution_path: Path to the .tar.gz file containing package metadata

    Returns:
        Tuple of ``(top_level_imports, project_name)``

    Raises:
        :py:exc:`.MissingDistributionMetadataFile`

    """
    top_level_imports = None
    project_name = None
    with tarfile.open(distribution_path) as tar:
        for tarinfo in tar:
            if tarinfo.isreg():
                if os.path.basename(tarinfo.name) == "top_level.txt":
                    f = tar.extractfile(tarinfo)
                    top_level_imports = _parse_top_level_imports_from_file(
                        distribution_path, f
                    )
                elif os.path.basename(tarinfo.name) == "PKG-INFO":
                    f = tar.extractfile(tarinfo)
                    project_name = _get_project_name_from_metadata_file(
                        distribution_path, f
                    )
                elif tarinfo.name.endswith(".egg-info/PKG-INFO"):
                    f = tar.extractfile(tarinfo)
                    project_name = _get_project_name_from_metadata_file(
                        distribution_path, f
                    )

            if top_level_imports is not None and project_name is not None:
                break

    if project_name is None:
        raise MissingDistributionMetadataFile(
            f"Could not find PKG-INFO in {distribution_path}"
        )
    elif top_level_imports is None:
        top_level_imports = [project_name]
        logger.debug(
            f"Could not find top_level.txt in {distribution_path}."
            f" Defaulting top level import list to {top_level_imports}"
        )

    return top_level_imports, project_name


def _get_package_names_from_zip(distribution_path: str) -> Tuple[List[str], str]:
    """Get the top-level import name and project name for a given .zip distribution

    Args:
        distribution_path: Path to the .zip file containing package metadata

    Returns:
        Tuple of ``(top_level_imports, project_name)``

    Raises:
        :py:exc:`.MissingDistributionMetadataFile`

    """
    zf = zipfile.ZipFile(distribution_path)
    top_level_imports = None
    project_name = None
    for name in zf.namelist():
        if os.path.basename(name) == "top_level.txt":
            with zf.open(name) as f:
                top_level_imports = _parse_top_level_imports_from_file(
                    distribution_path, f
                )
        elif os.path.basename(name) == "PKG-INFO":
            with zf.open(name) as f:
                project_name = _get_project_name_from_metadata_file(
                    distribution_path, f
                )

        if top_level_imports is not None and project_name is not None:
            break

    if project_name is None:
        raise MissingDistributionMetadataFile(
            f"Could not find PKG-INFO in {distribution_path}"
        )
    elif top_level_imports is None:
        top_level_imports = [project_name]
        logger.debug(
            f"Could not find top_level.txt in {distribution_path}."
            f" Defaulting top level import list to {top_level_imports}"
        )

    return top_level_imports, project_name


def _get_package_names_for_distribution(
    distribution_path: str
) -> Tuple[List[str], str]:
    """Get the top-level import names and project name for a given distribution file path

    Args:
        distribution_path: Path to the .whl, .tar.gz, or .zip file containing package
            metadata

    Returns:
        Tuple of ``(top_level_imports, project_name)``

    Raises:
        :py:exc:`.UnsupportedDistributionFormat`

    """
    if distribution_path.endswith(".whl"):
        return _get_package_names_from_wheel(distribution_path)
    elif distribution_path.endswith(".tar.gz") or distribution_path.endswith(
        ".tar.bz2"
    ):
        return _get_package_names_from_tar(distribution_path)
    elif distribution_path.endswith(".zip"):
        return _get_package_names_from_zip(distribution_path)

    raise UnsupportedDistributionFormat(
        f"Unsupported Python distribution file: {distribution_path}"
    )


def _get_import_map_for_requirements(
    requirement_specifiers: List[str],
) -> Tuple[List[Exception], Dict[str, str]]:
    """Get a map of top-level import name to project name for a list of requirements

    Args:
        requirement_specifiers: List of requirement specifiers like ``requests==1.2.3``

    Returns:
        Tuple with items:
        * List of exception objects, if any
        * Map of the top-level import name to the project name

    """
    import_map = {}
    with tempfile.TemporaryDirectory() as tmpdirname:
        logger.debug(f"Downloading Python packages to {tmpdirname}")
        # Download the wheels and tarballs for the requirements into a temp directory
        subprocess.run(
            [
                sys.executable,
                "-m",
                "pip",
                "download",
                "-d",
                tmpdirname,
                "--no-deps",
                *requirement_specifiers,
            ],
            check=True,
        )
        distribution_paths = (
            list(glob.glob(f"{tmpdirname}/*.whl"))
            + list(glob.glob(f"{tmpdirname}/*.tar.gz"))
            + list(glob.glob(f"{tmpdirname}/*.tar.bz2"))
            + list(glob.glob(f"{tmpdirname}/*.zip"))
        )
        logger.debug(f"Found distribution paths: {distribution_paths}")
        # Process each downloaded distribution, extracting the top-level import name
        # and the project name to add to the map
        exceptions = []
        for distribution_path in distribution_paths:
            try:
                top_level_imports, project_name = _get_package_names_for_distribution(
                    distribution_path
                )
            except Exception as e:
                exceptions.append(e)
            else:
                for top_level_import in top_level_imports:
                    logger.debug(
                        f"Found map of {top_level_import} => {project_name} for"
                        f" distribution {distribution_path}"
                    )
                    import_map[top_level_import] = project_name

    return exceptions, import_map


def update_third_party_import_map() -> None:
    """Update the third-party import map file.

    This will determine which keys should be added or dropped based on the
    requirements.txt file. Therefore, :py:func:`generate_3rdparty_requirements` should
    be run prior to this function.

    """
    logger.info("Updating third-party import map")

    with PROJECT_CONFIG.third_party_requirements_path.open() as f:
        requirements = list(pkg_resources.parse_requirements(f.read()))

    existing_project_names = set(THIRD_PARTY_IMPORT_MAP.values())
    current_project_names = set(req.project_name for req in requirements)

    # New requirements for which we need to go resolve an import name
    new_project_names = current_project_names - existing_project_names
    logger.info(
        f"Found {len(new_project_names)} new requirement(s) to resolve: {new_project_names}"
    )

    # Old requirements that should be removed from the map
    old_project_names = existing_project_names - current_project_names
    logger.info(
        f"Found {len(old_project_names)} requirement(s) to remove: {old_project_names}"
    )

    if len(new_project_names) == 0 and len(old_project_names) == 0:
        logger.info("No updates needed for third-party import map")
        return

    # Create a copy of the import map that we'll mutate
    import_map = deepcopy(THIRD_PARTY_IMPORT_MAP)
    import_map_inverse = {v: k for k, v in THIRD_PARTY_IMPORT_MAP.items()}

    # Remove old requirements
    for project_name in old_project_names:
        del import_map[import_map_inverse[project_name]]

    new_requirement_specifiers = [
        str(req) for req in requirements if req.project_name in new_project_names
    ]
    import_map_exceptions = []
    if len(new_requirement_specifiers) > 0:
        import_map_exceptions, import_map_updates = _get_import_map_for_requirements(
            new_requirement_specifiers
        )
        import_map.update(import_map_updates)

    with PROJECT_CONFIG.third_party_import_map_path.open("w") as f:
        json.dump(import_map, f, sort_keys=True, indent=2)

    logger.info("Finished updating third-party import map")

    if len(import_map_exceptions) > 0:
        messages = "\n" + "\n".join([str(e) for e in import_map_exceptions])
        raise DistributionError(
            f"Failed to process all Python distributions: {messages}"
        )
