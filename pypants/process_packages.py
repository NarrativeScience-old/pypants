"""Contains package processor class"""
import copy
import importlib.util
import logging
from multiprocessing import Pool
import os
from pathlib import Path
import re
from typing import Dict, List, Optional, Tuple

import networkx as nx

from .build_targets import (
    BUILD_TARGET_MAP,
    PY2SFNProjectPackage,
    PythonLibraryPackage,
    PythonPackage,
    PythonRequirement,
    PythonTestPackage,
)
from .config import Config, PROJECT_CONFIG
from .exceptions import (
    CircularImportsFound,
    DuplicateTarget,
    MultipleSourcePackagesFound,
    NoTargetFound,
)
from .util import gather_dependencies_from_module, write_build_file

logger = logging.getLogger(__name__)

# Number of workers to use for various multiprocessing pools
PROCESSES = max(1, os.cpu_count() - 1)


class PackageProcessor:
    """Class with methods for processing internal Python packages in order to:

    * Check for circular imports
    * Generate Pants BUILD files
    * Determine package dependencies
    """

    def __init__(self) -> None:
        # Map of target key to instance of a Python package build target
        self._targets: Dict[str, PythonPackage] = {}
        # Graph of targets
        self._target_graph: nx.DiGraph = None

    def get_target(self, target_key: str) -> PythonPackage:
        """Get a registered target by key

        Args:
            target_key: Key under which the target was registered

        Returns:
            target/package object

        """
        return self._targets[target_key]

    def register_packages(self) -> None:
        """Register targets and their dependencies.

        This should be called before performing an action with the packages.
        """
        self._register_task_targets_code()
        self._register_task_targets_py2sfn_projects()
        self._register_task_targets_tests()
        self._register_extra_targets()
        self._gather_dependencies()
        self._build_target_graph()

    def _gather_dependencies(self) -> None:
        """Gather dependencies for each target"""
        logger.info("Gathering dependencies")

        # Collect a list of (build target, Python module) pairs from *all* the targets
        target_paths: List[Tuple[PythonPackage, str]] = []
        for target in self._targets.values():
            target_paths.extend(target.find_target_paths())

        # Create a pool of workers that will parse imports from each Python module
        # path.
        paths = [path for _, path in target_paths]
        with Pool(processes=PROCESSES) as pool:
            # Return a list of sets containing imported package names
            imported_package_names_per_path = pool.map(
                gather_dependencies_from_module, paths
            )

        # For each target path / package name pair, process and add the dependency to
        # the target's set of dependencies.
        for (target, _), package_names in zip(
            target_paths, imported_package_names_per_path
        ):
            for package_name in package_names:
                target.add_dependency(self._targets, package_name)

        # Allow each target to set extra dependencies based on their own custom logic.
        # For most targets this will be a no-op.
        for target in self._targets.values():
            target.set_extra_dependencies(self._targets)

    def generate_build_files(self, target_pattern: Optional[str] = None) -> None:
        """Generate BUILD files.

        You must have already called :py:meth:`.register_packages`.

        Args:
            target_pattern: If provided, BUILD files are only generated for targets with
                keys matching the pattern

        """
        logger.info("Generating BUILD files")
        trees_to_write = []
        for key, target in self._targets.items():
            if not target_pattern or re.search(target_pattern, key):
                tree = target.generate_build_file()
                if tree is not None:
                    trees_to_write.append((tree, target.build_file))

        # Create a pool of workers that will render, format, and write each AST module
        # tree to disk.
        with Pool(processes=PROCESSES) as pool:
            pool.starmap(write_build_file, trees_to_write)

    def generate_build_file(self, target_key: str) -> None:
        """Generate BUILD file for a single target.

        You must have already called :py:meth:`.register_packages`.
        """
        target = self._targets[target_key]
        tree = target.generate_build_file()
        write_build_file(tree, target.build_file)

    def _register_task_targets_code(self) -> None:
        """Register task targets for code packages

        This iterates through various directories looking for a setup.py file. If it
        finds one, it means we've found a Python package and can register a build
        target.
        """
        logger.info("Registering code targets")

        setup_py_paths: List[Tuple[str, Path]] = []
        for top_dir_name in PROJECT_CONFIG.top_dirs:
            logger.debug(f"Walking {top_dir_name}")
            for dirpath, dirnames, filenames in os.walk(top_dir_name):
                if os.path.basename(dirpath) in PROJECT_CONFIG.ignore_dirs:
                    # Empty the list of directories so os.walk does not recur
                    dirnames.clear()
                else:
                    for filename in filenames:
                        if filename == "setup.py":
                            setup_py_paths.append(
                                (top_dir_name, Path(dirpath).joinpath(filename))
                            )

        for top_dir_name, setup_py_path in setup_py_paths:
            logger.debug(f"Registering {setup_py_path}")

            src_dir = setup_py_path.parent.joinpath("src")
            if not src_dir.is_dir():
                continue
            src_entries = [
                src_entry
                for src_entry in os.scandir(src_dir)
                if (
                    src_entry.is_dir()
                    and "egg-info" not in src_entry.path
                    and "pycache" not in src_entry.path
                )
            ]
            if len(src_entries) == 0:
                logger.debug(f"No entries found in {src_dir}")
                continue
            elif len(src_entries) > 1:
                raise MultipleSourcePackagesFound(
                    f"More than one package found in {src_dir}:"
                    f" {src_entries}. This could be caused by old git"
                    " state. Either manually clean up the packages or"
                    " run `git clean -fxd` if you are OK with a"
                    " completely clean slate."
                )

            src_entry = src_entries[0]
            package_name = os.path.basename(src_entry.path)
            config = Config(setup_py_path.parent)
            package_type = config.type
            if package_type is None:
                # Default the package type to "library"
                PythonPackageClass = PythonLibraryPackage
                config.set("package", "type", "library")
            else:
                PythonPackageClass = BUILD_TARGET_MAP[package_type]
            target = PythonPackageClass(
                target_type="code",
                build_template=top_dir_name,
                top_dir_name=top_dir_name,
                package_dir_name=str(setup_py_path.parent.relative_to(top_dir_name)),
                package_path=src_entry.path,
                package_name=package_name,
                build_dir=str(src_dir),
                config=config,
            )
            if target.key in PROJECT_CONFIG.ignore_targets:
                logger.debug(f"Ignoring {target}")
            elif package_name in self._targets:
                raise DuplicateTarget(
                    f"Duplicate target found for {package_name}. Check the"
                    " git repository for old folders that have the same"
                    " name."
                )
            else:
                self._targets[package_name] = target
                logger.debug(f"Registered target {target}")

    def _register_task_targets_tests(self) -> None:
        """Register task targets for tests

        This iterates through the previously registered build targets for code and
        registers test targets if they exist.
        """
        logger.info("Registering test targets")
        _targets = copy.copy(self._targets)
        for code_target in _targets.values():
            for tests_dir_type in ["unit", "functional", "component"]:
                tests_dir = os.path.join(
                    code_target.top_dir_name,
                    code_target.package_dir_name,
                    "tests",
                    tests_dir_type,
                )
                try:
                    os.scandir(tests_dir)
                except FileNotFoundError:
                    logger.debug(f"No tests found in {tests_dir}")
                else:
                    target = PythonTestPackage(
                        target_type="tests",
                        build_template="tests",
                        top_dir_name=code_target.top_dir_name,
                        package_dir_name=code_target.package_dir_name,
                        package_path=tests_dir,
                        package_name=tests_dir,
                        build_dir=tests_dir,
                        extra_tags={tests_dir_type},
                        code_target_package_name=code_target.package_name,
                    )
                    if target.key in PROJECT_CONFIG.ignore_targets:
                        logger.debug(f"Ignoring {target}")
                    else:
                        self._targets[tests_dir] = target
                        logger.debug(f"Registered target {target}")

    def _register_task_targets_py2sfn_projects(self) -> None:
        """Register py2sfn project targets.

        This looks for stepfunctions/projects/* folders. The BUILD file in each project
        consists of a generic ``target`` that only serves to point to the underlying
        tasks.
        """
        project_paths = Path("stepfunctions/projects").glob("*/project.sfn")
        for project_sfn in project_paths:
            project_path = project_sfn.parent
            target = PY2SFNProjectPackage(
                target_type="py2sfn-project",
                build_template="py2sfn-project",
                top_dir_name="stepfunctions/projects",
                package_dir_name=project_path.name,
                package_path=str(project_path),
                package_name=str(project_path),
                build_dir=str(project_path),
            )
            if target.key in PROJECT_CONFIG.ignore_targets:
                logger.debug(f"Ignoring {target}")
            elif target.key in self._targets:
                raise DuplicateTarget(
                    f"Duplicate target found for {target.key}. Check the"
                    " git repository for old folders that have the same"
                    " name."
                )
            else:
                self._targets[target.key] = target
                logger.debug(f"Registered target {target}")

    def _register_extra_targets(self) -> None:
        """Register extra project-specific targets.

        If the project has a ``.pypants/targets.py`` module defined with a top-level ``register_extra_targets``
        function defined, this method will call it and update the dictionary of build targets.
        """
        targets_path = PROJECT_CONFIG.config_dir_path.joinpath(".pypants/targets.py")
        if not targets_path.exists():
            logger.debug(f"No project targets.py found at {targets_path}")
            return

        logger.info("Registering extra project-specific targets")
        spec = importlib.util.spec_from_file_location("targets", str(targets_path))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        targets = mod.register_extra_targets()
        existing_target_names = set(self._targets.keys()).intersection(
            set(targets.keys())
        )
        if len(existing_target_names) > 0:
            logger.warning(
                f"Extra target(s) already registered: {', '.join(existing_target_names)}"
            )
        self._targets.update(targets)

    def _build_target_graph(self) -> None:
        """Build a graph of package targets.

        This is used to check for cycles and compute dependencies.
        """
        G = nx.DiGraph()
        for target in self._targets.values():
            G.add_node(target)
            for dependency in target.dependencies:
                G.add_edge(target, dependency)
        self._target_graph = G

    def ensure_no_circular_imports(self) -> None:
        """Ensure there are no circular imports in any of the processed packages

        You must have already called :py:meth:`.register_packages`.

        Raises:
            :py:exec:`.CircularImportsFound` if any circular imports were found

        """
        logger.info("Ensuring no circular imports")
        cycles = list(nx.simple_cycles(self._target_graph))
        if len(cycles) > 0:
            raise CircularImportsFound(cycles)

    def compute_package_dependencies(
        self, target_key: str, include_3rdparty: bool = False
    ) -> List[PythonPackage]:
        """Compute a topologically-sorted list of dependencies for a given target.

        Args:
            target_key: Key of the registered build target
            include_3rdparty: Whether to include or exclude 3rdparty requirements in
                the list of dependencies

        Returns:
            list of PythonPackage instances sorted topologically

        """
        try:
            target = self._targets[target_key]
        except KeyError:
            raise NoTargetFound(
                f"No target registered named {target_key}."
                f" Available targets: {', '.join(sorted(self._targets.keys()))}"
            )

        dependencies = nx.descendants(self._target_graph, target)
        # Create a new graph with only the dependencies so we can sort
        subgraph = nx.DiGraph(self._target_graph.subgraph(dependencies))
        dependencies = list(nx.topological_sort(subgraph))
        if not include_3rdparty:
            dependencies = [
                d for d in dependencies if not isinstance(d, PythonRequirement)
            ]

        return dependencies
