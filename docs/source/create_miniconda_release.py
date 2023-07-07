import datetime
import urllib.request
import json

from packaging.version import Version
from pathlib import Path
from jinja2 import Template

SOURCE_DIR = Path(__file__).parent
RELEASE_DIR = SOURCE_DIR / "miniconda_releases"

RELEASE_NOTES_TEMPLATE = SOURCE_DIR / "miniconda_release_notes.rst.jinja2"
RELEASE_NOTES_RST = SOURCE_DIR / "miniconda_release_notes.rst"
MINICONDA_RST_TEMPLATE = SOURCE_DIR / "miniconda.rst.jinja2"
MINICONDA_RST = SOURCE_DIR / "miniconda.rst"

FILES_URL = "https://repo.anaconda.com/miniconda/.files.json"

# Must be sorted in the order in which they appear on the Miniconda page
OPERATING_SYSTEMS = ("Windows", "macOS", "Linux")
# Confirm these are up-to-date.
PLATFORM_MAP = {
    "win64": {
        "operating_system": "Windows",
        "suffix": "Windows-x86_64.exe",
        "description": "Windows 64-bit",
    },
    "win32": {
        "operating_system": "Windows",
        "suffix": "Windows-x86.exe",
        "description": "Windows 32-bit",
        "miniconda_version": "4.12.0",  # win-32 will be frozen at version 4.12.0
    },
    "osx64_sh": {
        "operating_system": "macOS",
        "suffix": "MacOSX-x86_64.sh",
        "description": "macOS Intel x86 64-bit bash",
    },
    "osx64_pkg": {
        "operating_system": "macOS",
        "suffix": "MacOSX-x86_64.pkg",
        "description": "macOS Intel x86 64-bit pkg",
    },
    "osx_arm64_sh": {
        "operating_system": "macOS",
        "suffix": "MacOSX-arm64.sh",
        "description": "macOS Apple M1 64-bit bash",
    },
    "osx_arm64_pkg": {
        "operating_system": "macOS",
        "suffix": "MacOSX-arm64.pkg",
        "description": "macOS Apple M1 64-bit pkg",
    },
    "linux64": {
        "operating_system": "Linux",
        "suffix": "Linux-x86_64.sh",
        "description": "Linux 64-bit",
    },
    "linux_aarch64": {
        "operating_system": "Linux",
        "suffix": "Linux-aarch64.sh",
        "description": "Linux-aarch64 64-bit",
    },
    "linux_ppc64le": {
        "operating_system": "Linux",
        "suffix": "Linux-ppc64le.sh",
        "description": "Linux-ppc64le 64-bit",
    },
    "linux_s390x": {
        "operating_system": "Linux",
        "suffix": "Linux-s390x.sh",
        "description": "Linux-s390x 64-bit",
    },
}


def get_installer_info(release: Path) -> dict:
    """
    Process _info.json files output by constructor to get installer information,
    including the list of delivered packages
    """
    def get_package_list(dists: list[str]) -> list:
        #  The `dist` strings are of the format "<name>-<version>-<hash>_<build_num>.conda"
        packages = []
        for dist in dists:
            if dist.startswith("_"):
                continue
            pkg_name, pkg_version, pkg_split = dist[:-6].rsplit("-", 2)
            pkg_hash, pkg_build_num = pkg_split.split("_")
            package = {
                "name": pkg_name,
                "version": pkg_version,
                "hash": pkg_hash,
                "build_num": pkg_build_num
            }
            packages.append(package)
        return packages

    installer_info = {}
    for info_json in release.iterdir():
        if not info_json.name.endswith("_info.json"):
            continue
        info_dict = json.loads(info_json.read_text())
        info_dict["packages"] = get_package_list(info_dict["_dists"])
        platform = info_dict["_platform"]
        installer_type = info_dict["installer_type"]
        installer_info[platform,installer_type] = info_dict

    return installer_info


def sizeof_fmt(num, suffix="B"):
    for unit in ["", "Ki", "Mi", "Gi"]:
        if abs(num) < 1024.0:
            return "%3.1f %s%s" % (num, unit, suffix)
        num /= 1024.0
    return "%.1f %s%s" % (num, "Yi", suffix)


def get_supported_python_versions(miniconda_version, files_info):
    """
    Return python versions found in Miniconda installer file names
    for a particular Miniconda version.
    """
    py_versions = []
    for filename in files_info:
        if not f"_{miniconda_version}-" in filename or "py" not in filename:
            continue
        py_intermediate = filename.split("py")[1]
        py_version = py_intermediate.split("_")[0]
        py_version = f"{py_version[0]}.{py_version[1:]}"
        if py_version not in py_versions:
            py_versions.append(py_version)
    return py_versions


def get_miniconda_template_vars(files_info, release_info):
    """
    Returns a dict with sizes and SHA256 hashes for each
    installer built for the latest CONDA_VERSION.
    """
    info = {
        "conda_version": release_info["miniconda_version"].split("-")[0],
        "release_date": release_info["release_date"],
        "operating_systems": OPERATING_SYSTEMS,
        "py_versions": sorted(release_info["py_versions"], reverse=True, key=Version),
        "python_version": release_info["python_version"],
    }
    info["platforms"] = {(os,"latest"): [] for os in info["operating_systems"]}

    for platform_id, installer_data in PLATFORM_MAP.items():
        latest_installer = f"Miniconda3-latest-{installer_data['suffix']}"
        os = installer_data["operating_system"]
        info["platforms"][os,"latest"].append(installer_data.copy())
        info["platforms"][os,"latest"][-1]["hash"] = files_info[latest_installer]["sha256"]
        if "miniconda_version" not in installer_data:
            installer_data["miniconda_version"] = release_info["miniconda_version"]
        for py_version in info["py_versions"]:
            py = py_version.replace(".", "")
            full_installer = (
                f"Miniconda3-py{py}_{installer_data['miniconda_version']}-{installer_data['suffix']}"
            )

            if full_installer not in files_info:
                continue
            if (os, py_version) not in info["platforms"]:
                info["platforms"][os,py_version] = [installer_data.copy()]
            else:
                info["platforms"][os,py_version].append(installer_data.copy())
            installer = info["platforms"][os,py_version][-1]
            installer["size"] = sizeof_fmt(files_info[full_installer]["size"])
            installer["hash"] = files_info[full_installer]["sha256"]
            installer["full_installer"] = full_installer

    return info


def get_release_template_vars(miniconda_version, release_info, files_info):
    release_vars = {
        "miniconda_version": miniconda_version,
    }
    for (platform, ext), info in release_info.items():
        if "python_version" not in release_vars:
            for package in info["packages"]:
                if package["name"] == "python":
                    release_vars["python_version"] = package["version"]
                    break
        installer_file = Path(info["_outpath"]).name
        if "release_date" not in info and installer_file in files_info:
            mtime = files_info[installer_file]["mtime"]
            mdate = datetime.date.fromtimestamp(mtime)
            release_vars["release_date"] = mdate.strftime("%B %-d, %Y")
    py_versions = get_supported_python_versions(miniconda_version, files_info)
    release_vars["py_versions"] = sorted(py_versions, key=Version)
    return release_vars


def main():
    with urllib.request.urlopen(urllib.request.Request(url=FILES_URL)) as f:
        files_info = json.loads(f.read().decode("utf-8"))

    release_info = {}
    for release in RELEASE_DIR.iterdir():
        release_info[release.name] = get_installer_info(release)


    miniconda_vars = {}
    release_vars = {"release": []}
    for r, release in enumerate(sorted(release_info, reverse=True, key=Version)):
        template_vars = get_release_template_vars(release, release_info[release], files_info)
        release_vars["release"].append(template_vars)
        if r == 0:
            miniconda_vars = get_miniconda_template_vars(files_info, release_vars["release"][0])

    template_files = (RELEASE_NOTES_TEMPLATE, MINICONDA_RST_TEMPLATE)
    template_vars = (release_vars, miniconda_vars)
    out_files = (RELEASE_NOTES_RST, MINICONDA_RST)
    for template_file, template_dict, out_file in zip(template_files, template_vars, out_files):
        with open(template_file) as f:
            template_text = f.read()

        template = Template(template_text)
        rst_text = template.render(**template_dict)
        with open(out_file, "w") as f:
            f.write(rst_text)

if __name__ == "__main__":
     main()
