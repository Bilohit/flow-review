"""Only a cmdclass override: everything else stays in pyproject.toml.

setuptools has no pyproject.toml-level knob that excludes specific *.py modules from a
package -- `exclude-package-data` only filters non-code data files, never the *.py modules
`build_py` discovers by walking each package directory. Overriding `find_package_modules` is
the standard way to drop the colocated test_*.py/conftest.py files (about 290 KB) from the
wheel while leaving them in place for pytest, which imports them straight from source and
never goes through this build step.
"""
from setuptools import setup
from setuptools.command.build_py import build_py as _build_py


class build_py(_build_py):
    def find_package_modules(self, package, package_dir):
        modules = super().find_package_modules(package, package_dir)
        return [
            (pkg, name, path) for pkg, name, path in modules
            if not (name.startswith("test_") or name == "conftest")
        ]


if __name__ == "__main__":
    setup(cmdclass={"build_py": build_py})
