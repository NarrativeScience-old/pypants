"""Contains PythonLibraryPackage class"""
import ast

from .python_package import PythonPackage


class PythonLibraryPackage(PythonPackage):
    """Represents a Python library package build target in Pants

    A library is a package that is meant to be imported by other packages. It is not
    meant to be run as a script.
    """

    def generate_build_file_ast_node(self) -> ast.Module:
        """Generate a Pants BUILD file as an AST module node"""
        body = []
        # check if we have a resource target
        if self.config.resource_glob_path:
            body.append(self._generate_python_library_resources_ast_node())
        # Add in the lib
        body.append(
            self._generate_python_library_ast_node(
                globs_path=f"{self.package_name}/**/*.py"
            )
        )
        node = ast.Module(body=body)
        return node
