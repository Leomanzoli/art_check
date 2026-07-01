"""
Script de build para gerar o executável do ART Check.
Uso: python build.py
"""

import PyInstaller.__main__
import os
import sys
import shutil
import importlib.metadata

# Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DIST_DIR = os.path.join(BASE_DIR, "dist")
BUILD_DIR = os.path.join(BASE_DIR, "build")
SITE_PACKAGES = os.path.join(os.path.dirname(os.__file__), "site-packages")

# Encontrar diretórios dos pacotes
import streamlit
import st_aggrid
import altair

STREAMLIT_DIR = os.path.dirname(streamlit.__file__)
ST_AGGRID_DIR = os.path.dirname(st_aggrid.__file__)
ALTAIR_DIR = os.path.dirname(altair.__file__)


def find_dist_info(package_name):
    """Encontra o diretório .dist-info de um pacote."""
    try:
        d = importlib.metadata.distribution(package_name)
        return str(d._path)
    except importlib.metadata.PackageNotFoundError:
        return None


# Pacotes que precisam de metadados (.dist-info)
METADATA_PACKAGES = [
    "streamlit", "streamlit-aggrid", "altair", "pandas", "numpy",
    "openpyxl", "pyarrow", "packaging", "pillow", "tornado", "click",
    "toml", "jinja2", "protobuf", "requests", "pydeck", "watchdog",
    "gitpython", "blinker", "cachetools", "rich", "tenacity",
    "typing-extensions", "markupsafe", "charset-normalizer", "certifi",
    "urllib3", "idna", "attrs", "jsonschema", "jsonschema-specifications",
    "referencing", "rpds-py", "narwhals", "toolz",
]


def build():
    print("=" * 50)
    print("  Building ART Check executable...")
    print("=" * 50)

    # Coletar dist-info directories
    metadata_args = []
    for pkg in METADATA_PACKAGES:
        dist_path = find_dist_info(pkg)
        if dist_path and os.path.exists(dist_path):
            folder_name = os.path.basename(dist_path)
            metadata_args.append(f"--add-data={dist_path};{folder_name}")
            print(f"  [META] {pkg} -> {folder_name}")
        else:
            print(f"  [SKIP] {pkg} (not found)")

    # Tentar incluir pyarrow data
    extra_datas = []
    try:
        import pyarrow
        PYARROW_DIR = os.path.dirname(pyarrow.__file__)
        extra_datas.append(f"--add-data={PYARROW_DIR};pyarrow")
    except ImportError:
        pass

    args = [
        os.path.join(BASE_DIR, "launcher.py"),
        "--name=ART_Check",
        "--onedir",
        "--console",
        # Incluir os arquivos da aplicação
        f"--add-data={os.path.join(BASE_DIR, 'app.py')};.",
        f"--add-data={os.path.join(BASE_DIR, 'analysis.py')};.",
        f"--add-data={os.path.join(BASE_DIR, 'assets')};assets",
        f"--add-data={os.path.join(BASE_DIR, '.streamlit')};.streamlit",
        # Incluir pacotes com assets estáticos
        f"--add-data={STREAMLIT_DIR};streamlit",
        f"--add-data={ST_AGGRID_DIR};st_aggrid",
        f"--add-data={ALTAIR_DIR};altair",
        # Hidden imports necessários
        "--hidden-import=streamlit",
        "--hidden-import=streamlit.web.cli",
        "--hidden-import=streamlit.runtime",
        "--hidden-import=streamlit.runtime.scriptrunner",
        "--hidden-import=st_aggrid",
        "--hidden-import=altair",
        "--hidden-import=pandas",
        "--hidden-import=numpy",
        "--hidden-import=openpyxl",
        "--hidden-import=pyarrow",
        "--hidden-import=PIL",
        "--hidden-import=packaging",
        "--hidden-import=packaging.version",
        "--hidden-import=packaging.specifiers",
        "--hidden-import=packaging.requirements",
        "--hidden-import=importlib_metadata",
        "--hidden-import=pydeck",
        "--hidden-import=jsonschema",
        "--hidden-import=narwhals",
        # Coleta automática de submodulos
        "--collect-submodules=streamlit",
        "--collect-submodules=st_aggrid",
        "--collect-submodules=altair",
        "--collect-submodules=pydeck",
        # Opções de build
        "--onefile",
        "--noconfirm",
        "--clean",
        f"--distpath={DIST_DIR}",
        f"--workpath={BUILD_DIR}",
    ] + metadata_args + extra_datas

    print("PyInstaller args:")
    for a in args:
        print(f"  {a}")
    print()

    PyInstaller.__main__.run(args)

    # No modo --onefile os assets são embutidos no exe; nada a copiar.
    exe_path = os.path.join(DIST_DIR, "ART_Check.exe")

    print()
    print("=" * 50)
    print(f"  Build concluído!")
    print(f"  Executável em: {exe_path}")
    print(f"  Copie ART_Check.exe para o pen drive e execute diretamente.")
    print("=" * 50)


if __name__ == "__main__":
    build()
