"""Contains PY2SFNProjectPackage class"""
import ast
import logging
from pathlib import Path
from typing import Dict

from .base import BuildTarget
from .python_package import PythonPackage

logger = logging.getLogger(__name__)


class PY2SFNProjectPackage(PythonPackage):
    """Represents a py2sfn project build target in Pants"""

    def set_dependencies(self, targets: Dict[str, BuildTarget]) -> None:
        """Compute and set the collection of dependencies as a batch.

        We're overriding the base class method because the generic py2sfn project build
        target only needs to depend on the task packages.

        Args:
            targets: map of package name to instance of BuildTarget

        """
        logger.debug(f"Gathering dependencies for {self.key}")
        for task_package_path in Path(self.build_dir).glob("tasks/*/src/*"):
            package_name = task_package_path.name
            if package_name in targets:
                self.dependencies.add(targets[package_name])
                logger.debug(
                    f"Added dependency for existing target: {targets[package_name]}"
                )
        logger.debug(f"Dependencies for {self.key}: {self.dependencies}")

    def add_dependency(
        self, targets: Dict[str, BuildTarget], package_name: str
    ) -> None:
        """Add a new dependency to the set

        We're overriding the base class method because the generic py2sfn project build
        target only needs to depend on the task packages. Therefore, we don't want to
        process any nested Python modules.
        """
        pass

    def _generate_generic_target_node(self) -> ast.Expr:
        """Generate an AST node for a generic ``target`` Pants target"""
        node = ast.Expr(
            value=ast.Call(
                func=ast.Name(id="target"),
                args=[],
                keywords=[self._get_dependencies_keyword(), self._tags_keyword],
            )
        )
        return node

    def generate_build_file_ast_node(self) -> ast.Module:
        """Generate a Pants BUILD file as an AST module node"""
        node = ast.Module(body=[self._generate_generic_target_node()])
        return node
