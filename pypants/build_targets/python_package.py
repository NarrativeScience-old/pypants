"""Contains base PythonPackage class"""
import ast
import logging
import os
import re
from typing import Dict, List, Optional, Set

import astor

from ..config import Config, PROJECT_CONFIG  # noqa
from ..requirements import THIRD_PARTY_IMPORT_MAP  # noqa
from .base import BuildTarget  # noqa
from .requirement import PythonRequirement  # noqa

logger = logging.getLogger(__name__)


COOKIECUTTER_PATH_PATTERN = re.compile(r"\{\{cookiecutter")


class PythonPackage(BuildTarget):
    """Represents a Python package (e.g. lib or test) build target in Pants"""

    def __init__(
        self,
        target_type: str,
        build_template: str,
        top_dir_name: str,
        package_dir_name: str,
        build_dir: str,
        package_path: str,
        package_name: str,
        rendered_package_name: Optional[str] = None,
        extra_tags: Optional[Set] = None,
        config: Optional[Config] = None,
        build_file_extension: str = "",
    ) -> None:
        """
        Args:
            target_type: Target type. One of: code, tests
            build_template: Key of the build template, e.g. lib
            top_dir_name: Top directory name, e.g. lib
            package_dir_name: Package directory name, e.g. python_core
            build_dir: Directory where the BUILD file will be stored,
                e.g. lib/python_core/src
            package_path: Path to the package code,
                e.g. lib/python_core/src/ns_python_core
            package_name: Package name, e.g. ns_python_core
            rendered_package_name: Package name to render into the BUILD file. This can
                be set if there's a conflict between the package name and the build
                directory. e.g. ns_python_core_lib
            extra_tags: Set of extra tags to include in the BUILD file in addition to
                the standard set
            config: Configuration for this package, potentially loaded from a
                .pypants.cfg file. If not provided it will be loaded.
            build_file_extension: Extension to add to the BUILD file name

        """
        self.target_type = target_type
        self.build_template = build_template
        self.top_dir_name = top_dir_name
        self.package_dir_name = package_dir_name
        self.package_dir_path = PROJECT_CONFIG.config_dir_path.joinpath(
            self.top_dir_name, self.package_dir_name
        )
        self.build_dir = build_dir
        self.build_file = os.path.join(self.build_dir, f"BUILD{build_file_extension}")
        self.package_path = package_path
        self.package_name = package_name
        self.rendered_package_name = (
            rendered_package_name
            if rendered_package_name is not None
            else self.package_name
        )

        # This string will be used as an identifier for the build target
        self.key = self.build_dir

        # Set of dependencies to be gathered later
        self.dependencies = set()

        self.config = config or Config(self.package_dir_path)

        tags = {"python", self.target_type, self.top_dir_name}
        if extra_tags is not None:
            tags.update(extra_tags)
        tags.update(self.config.extra_tags)
        self.tags = tags

    def set_dependencies(self, targets: Dict[str, BuildTarget]) -> None:
        """Compute and set the collection of dependencies as a batch.

        This implementation just reinitializes the dependencies attribute. A
        child class may choose to implement this method and skip the ``add_dependency``
        method.

        Args:
            targets: map of package name to instance of BuildTarget

        """
        self.dependencies = set()

    def add_dependency(
        self, targets: Dict[str, BuildTarget], package_name: str
    ) -> None:
        """Add a new dependency to the set

        A child class may choose to implement ``set_dependencies`` and skip this method.

        Args:
            targets: map of package name to instance of BuildTarget
            package_name: dependency package name, as parsed from an import statement

        """
        logger.debug(f"Processing {package_name}")
        if package_name in targets and package_name != self.package_name:
            self.dependencies.add(targets[package_name])
            logger.debug(
                f"Added dependency for existing target: {targets[package_name]}"
            )
        elif package_name in THIRD_PARTY_IMPORT_MAP:
            self.dependencies.add(
                PythonRequirement(THIRD_PARTY_IMPORT_MAP[package_name])
            )
            logger.debug(
                f"Added third-party dependency: {THIRD_PARTY_IMPORT_MAP[package_name]}"
            )

    def _parse_build_ast(self) -> Optional[ast.Module]:
        """Parse AST of BUILD file if it exists

        Returns:
            AST of the BUILD file or ``NoneType`` if the file doesn't exist

        """
        try:
            return astor.code_to_ast.parse_file(self.build_file)
        except FileNotFoundError:
            logger.error(f"Could not find {self.build_file}")
            return None

    def generate_build_file(self) -> Optional[ast.Module]:
        """Generate a Pants BUILD file for the build target

        Returns:
            AST module node representing the BUILD file

        """
        if not self.config.generate_build_file:
            logger.debug(f"Not writing BUILD file to {self.build_file}")
            return None

        return self.generate_build_file_ast_node()

    def generate_build_file_ast_node(self) -> ast.Module:
        """Generate a Pants BUILD file as an AST module node"""
        raise NotImplementedError("generate_build_file_ast_node")

    def _get_dependencies_keyword(
        self, include_extra_dependencies: bool = True
    ) -> ast.keyword:
        """Build the AST node representing the dependencies keyword argument

        Args:
            include_extra_dependencies: Flag for whether the extra dependencies
                specified in the config file should be included

        """
        dependencies = set(
            dependency.dependency_target for dependency in self.dependencies
        )
        if include_extra_dependencies:
            dependencies.update(self.config.extra_dependencies)
        dependencies = sorted(list(dependencies), key=lambda d: str(d).lower())
        return ast.keyword(
            arg="dependencies", value=ast.List(elts=[ast.Str(d) for d in dependencies])
        )

    @property
    def _tags_keyword(self) -> ast.keyword:
        """AST node representing the tags keyword argument"""
        return ast.keyword(
            arg="tags", value=ast.Set(elts=[ast.Str(t) for t in sorted(self.tags)])
        )

    def _generate_python_library_resources_ast_node(self, globs_path: str = "**/*"):
        """Generate an AST node for a python resource target

        Args:
            globs_path: The path to look for resources at

        Returns:
            AST expression node

        """
        keywords = [ast.keyword(arg="name", value=ast.Str("resources"))]
        # gather the globs if present in the config, otherwise the sources are default
        if self.config.resource_glob_path:
            sources = []
            for path in self.config.resource_glob_path.split(" "):
                sources.append(ast.Str(path))
            keywords.append(ast.keyword(arg="sources", value=ast.List(elts=sources)))
        else:
            keywords.append(
                ast.keyword(arg="sources", value=ast.List(elts=[ast.Str(globs_path)]))
            )
        # create our node of resources
        node = ast.Expr(
            value=ast.Call(func=ast.Name(id="resources"), args=[], keywords=keywords)
        )
        return node

    def _generate_python_library_ast_node(
        self,
        name: Optional[str] = None,
        globs_path: str = "**/*.py",
        include_extra_dependencies: bool = True,
    ) -> ast.Expr:
        """Generate an AST node for a python_library Pants target

        Args:
            name: Name of the library target. If not provided, no name will be set.
            globs_path: File globs to include in the target. Defaults to everything.
            include_extra_dependencies: Flag for whether the extra dependencies
                specified in the config file should be included. This should usually be
                True except when generating a test library target.

        Returns:
            AST expression node

        """
        keywords = [
            self._get_dependencies_keyword(
                include_extra_dependencies=include_extra_dependencies
            ),
            ast.keyword(arg="sources", value=ast.List(elts=[ast.Str(globs_path)])),
            self._tags_keyword,
        ]
        if name is not None:
            keywords.insert(0, ast.keyword(arg="name", value=ast.Str(name)))
        node = ast.Expr(
            value=ast.Call(
                func=ast.Name(id="python_library"), args=[], keywords=keywords
            )
        )
        return node

    def _generate_python_binary_wrapper_node(
        self,
        name: str,
        entry_point: Optional[str] = None,
        dependencies: Optional[List[str]] = None,
    ) -> ast.Expr:
        """Generate an AST node for a python_binary Pants target with an entry point

        See: https://www.pantsbuild.org/python_readme.html#python_binary-entry_point

        Args:
            name: Name of the binary, e.g. unittest
            entry_point: Entrypoint module in package, e.g. unittest. Defaults to the
                name
            dependencies: List of targets for this wrapper to depend on

        Returns:
            AST expression node

        """
        if entry_point is None:
            entry_point = name

        node = ast.Expr(
            value=ast.Call(
                func=ast.Name(id="python_binary"),
                args=[],
                keywords=[
                    ast.keyword(arg="name", value=ast.Str(name)),
                    ast.keyword(arg="entry_point", value=ast.Str(entry_point)),
                    ast.keyword(
                        arg="dependencies",
                        value=ast.List(elts=[ast.Str(d) for d in dependencies]),
                    ),
                    ast.keyword(
                        arg="zip_safe", value=ast.NameConstant(self.config.zip_safe)
                    ),
                ],
            )
        )
        return node
