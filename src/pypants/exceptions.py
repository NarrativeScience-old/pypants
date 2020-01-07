"""Contains exception classes"""


class CircularImportsFound(Exception):
    """Raised when circular imports were found processing build targets"""

    pass


class NoBuildDependenciesFound(Exception):
    """Raised when the dependencies argument could not be found in a BUILD file AST"""

    pass


class DistributionError(Exception):
    """Raised when a Python distribution can't be parsed"""

    pass


class UnsupportedDistributionFormat(DistributionError):
    """Raised when the distribution file is something other than a .whl or .tar.gz"""

    pass


class MissingDistributionMetadataFile(DistributionError):
    """Raised when there is a missing metadata file in a .whl or .tar.gz"""

    pass


class NoProjectName(Exception):
    """Raised when no project name could be parsed from distribution metadata"""

    pass


class InvalidTopLevelFile(Exception):
    """Raised when a top_level.txt file could not be interpreted"""

    pass


class MultipleSourcePackagesFound(Exception):
    """Raised when more than one package is found in src/"""

    pass


class DuplicateTarget(Exception):
    """Raised when attempting to register a target that has an existing key"""

    pass


class NoConsoleScriptFound(Exception):
    """Raised when no console_scripts are found in setup.py for a binary target"""

    pass


class NoTargetFound(Exception):
    """Raised when no target could be found in the registered graph of targets"""

    pass
