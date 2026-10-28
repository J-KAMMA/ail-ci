import json
import shutil
from pathlib import Path

from setuptools import setup
from setuptools.command.build_py import build_py as _build_py

REPO = Path(__file__).resolve().parent
SRC = REPO / "AIL_CURRENT"
MANIFEST = json.loads((SRC / "MANIFEST.json").read_text(encoding="utf-8"))
UNPACKAGED = {
    "python/pkg-v12/bench.py",
    "python/pkg-v12/test_all.py",
    "python/pkg-v12/test_pipeline.py",
}
SELECTED = [name for name in MANIFEST["sdk_files"] if name not in UNPACKAGED]
ROOT_MODULES = {name for name in SELECTED if "/" not in name and name.endswith(".py")}
DATA_FILES = [name for name in SELECTED if name not in ROOT_MODULES]
LICENSE_FILES = ("LICENSE-APACHE", "LICENSE-MIT")


class build_py(_build_py):
    """Install exactly the SDK selection, with a MANIFEST that describes the installed copy."""

    def find_package_modules(self, package, package_dir):
        modules = super().find_package_modules(package, package_dir)
        if package != "ail_lang":
            return modules
        return [item for item in modules if item[1] + ".py" in SELECTED]

    def run(self):
        destination = Path(self.build_lib) / "ail_lang"
        if destination.exists():
            shutil.rmtree(destination)
        super().run()
        pins = MANIFEST["sha256"]
        for name in DATA_FILES:
            source = SRC / name
            target = destination / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
        for name in LICENSE_FILES:
            shutil.copyfile(REPO / name, destination / name)
        packaged = set(SELECTED)
        installed = dict(MANIFEST)
        installed["sdk_files"] = sorted(packaged)
        installed["sha256"] = {name: pins[name] for name in sorted(packaged)}
        installed["files"] = {name: pins[name] for name in sorted(packaged)
                              if name in MANIFEST.get("files", {})}
        (destination / "MANIFEST.json").write_text(
            json.dumps(installed, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


setup(cmdclass={"build_py": build_py})
