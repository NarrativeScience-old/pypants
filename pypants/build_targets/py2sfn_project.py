"""Contains PY2SFNProjectPackage class"""
import ast
import logging
from pathlib import Path
from typing import Dict, List, Tuple

import astor
from fluxio_parser import parse_project_tree

from .base import BuildTarget
from .python_package import PythonPackage

logger = logging.getLogger(__name__)


class PY2SFNProjectPackage(PythonPackage):
    """Represents a py2sfn project build target in Pants"""

    def find_target_paths(self) -> List[Tuple["PythonPackage", str]]:
        """Find a list of target paths for parsing dependencies

        This implementation returns only the project.sfn file since that defines all the
        dependencies.

        Returns:
            list of tuples with items:
            * the current target (to indicate the owner)
            * the path to the file that will be parsed

        """
        return [(self, str(Path(self.build_dir).joinpath("project.sfn")))]

    def set_extra_dependencies(self, targets: Dict[str, BuildTarget]) -> None:
        """Set extra dependencies on the target

        We need to parse the project.sfn file to add dependencies on the packages
        specified in the ECS worker `spec` attribute.

        Args:
            targets: map of package name to instance of BuildTarget

        """
        project_sfn_file = Path(self.build_dir).joinpath("project.sfn")
        logger.debug(f"Parsing {project_sfn_file}")
        tree = astor.code_to_ast.parse_file(project_sfn_file)
        script_visitor = parse_project_tree(tree)
        for task_visitor in script_visitor.task_visitors.values():
            if task_visitor.attributes["service"] == "ecs:worker":
                # The `spec` attribute is formatted like `my_package.module:ClassName`.
                # We want to extract "my_package"
                module, _ = task_visitor.attributes["spec"].split(":")
                package_name = module.split(".")[0]
                logger.debug(f"Found ecs:worker dependency on {package_name}")
                self.add_dependency(targets, package_name)

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
