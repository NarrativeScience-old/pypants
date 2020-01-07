from pypants.generators.base import PythonPackageGenerator


class LibraryPackageGenerator(PythonPackageGenerator):
    """Generator for a Python library package"""

    PACKAGE_TYPE = "library"
    TOP_LEVEL_DIR = "packages"
