"""Compatibility shim for tooling that still invokes setup.py directly.

All package metadata (version, dependencies, extras, classifiers, package
data) lives in ``pyproject.toml`` as the single source of truth. This avoids
the version drift that previously left setup.py pinned to an old release while
pyproject.toml moved ahead.
"""

from setuptools import setup

setup()
