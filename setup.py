import json
from pathlib import Path

from setuptools import setup
from setuptools.command.build_py import build_py as _build_py

REPO = Path(__file__).resolve().parent
SDK_FILES = set(json.loads((REPO / "AIL_CURRENT" / "MANIFEST.json").read_text(encoding="utf-8"))["sdk_files"])


class build_py(_build_py):
    def find_package_modules(self, package, package_dir):
        modules = super().find_package_modules(package, package_dir)
        if package != "ail_lang":
            return modules
        return [item for item in modules if item[1] + ".py" in SDK_FILES]


setup(cmdclass={"build_py": build_py})
