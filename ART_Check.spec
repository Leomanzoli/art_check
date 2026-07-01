# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_submodules

hiddenimports = ['streamlit', 'streamlit.web.cli', 'streamlit.runtime', 'streamlit.runtime.scriptrunner', 'st_aggrid', 'altair', 'pandas', 'numpy', 'openpyxl', 'pyarrow', 'PIL', 'packaging', 'packaging.version', 'packaging.specifiers', 'packaging.requirements', 'importlib_metadata', 'pydeck', 'jsonschema', 'narwhals']
hiddenimports += collect_submodules('streamlit')
hiddenimports += collect_submodules('st_aggrid')
hiddenimports += collect_submodules('altair')
hiddenimports += collect_submodules('pydeck')


a = Analysis(
    ['D:\\Programas\\ART_Check\\launcher.py'],
    pathex=[],
    binaries=[],
    datas=[('D:\\Programas\\ART_Check\\app.py', '.'), ('D:\\Programas\\ART_Check\\analysis.py', '.'), ('D:\\Programas\\ART_Check\\assets', 'assets'), ('D:\\Programas\\ART_Check\\.streamlit', '.streamlit'), ('C:\\Users\\leoma\\AppData\\Local\\Programs\\Python\\Python312\\Lib\\site-packages\\streamlit', 'streamlit'), ('C:\\Users\\leoma\\AppData\\Local\\Programs\\Python\\Python312\\Lib\\site-packages\\st_aggrid', 'st_aggrid'), ('C:\\Users\\leoma\\AppData\\Local\\Programs\\Python\\Python312\\Lib\\site-packages\\altair', 'altair'), ('C:\\Users\\leoma\\AppData\\Local\\Programs\\Python\\Python312\\Lib\\site-packages\\streamlit-1.54.0.dist-info', 'streamlit-1.54.0.dist-info'), ('C:\\Users\\leoma\\AppData\\Local\\Programs\\Python\\Python312\\Lib\\site-packages\\streamlit_aggrid-1.2.1.post2.dist-info', 'streamlit_aggrid-1.2.1.post2.dist-info'), ('C:\\Users\\leoma\\AppData\\Local\\Programs\\Python\\Python312\\Lib\\site-packages\\altair-6.0.0.dist-info', 'altair-6.0.0.dist-info'), ('C:\\Users\\leoma\\AppData\\Local\\Programs\\Python\\Python312\\Lib\\site-packages\\pandas-2.3.3.dist-info', 'pandas-2.3.3.dist-info'), ('C:\\Users\\leoma\\AppData\\Local\\Programs\\Python\\Python312\\Lib\\site-packages\\numpy-1.26.4.dist-info', 'numpy-1.26.4.dist-info'), ('C:\\Users\\leoma\\AppData\\Local\\Programs\\Python\\Python312\\Lib\\site-packages\\openpyxl-3.1.5.dist-info', 'openpyxl-3.1.5.dist-info'), ('C:\\Users\\leoma\\AppData\\Local\\Programs\\Python\\Python312\\Lib\\site-packages\\pyarrow-23.0.1.dist-info', 'pyarrow-23.0.1.dist-info'), ('C:\\Users\\leoma\\AppData\\Local\\Programs\\Python\\Python312\\Lib\\site-packages\\packaging-25.0.dist-info', 'packaging-25.0.dist-info'), ('C:\\Users\\leoma\\AppData\\Local\\Programs\\Python\\Python312\\Lib\\site-packages\\pillow-12.0.0.dist-info', 'pillow-12.0.0.dist-info'), ('C:\\Users\\leoma\\AppData\\Local\\Programs\\Python\\Python312\\Lib\\site-packages\\tornado-6.5.4.dist-info', 'tornado-6.5.4.dist-info'), ('C:\\Users\\leoma\\AppData\\Local\\Programs\\Python\\Python312\\Lib\\site-packages\\click-8.3.1.dist-info', 'click-8.3.1.dist-info'), ('C:\\Users\\leoma\\AppData\\Local\\Programs\\Python\\Python312\\Lib\\site-packages\\toml-0.10.2.dist-info', 'toml-0.10.2.dist-info'), ('C:\\Users\\leoma\\AppData\\Local\\Programs\\Python\\Python312\\Lib\\site-packages\\jinja2-3.1.6.dist-info', 'jinja2-3.1.6.dist-info'), ('C:\\Users\\leoma\\AppData\\Local\\Programs\\Python\\Python312\\Lib\\site-packages\\protobuf-6.33.5.dist-info', 'protobuf-6.33.5.dist-info'), ('C:\\Users\\leoma\\AppData\\Local\\Programs\\Python\\Python312\\Lib\\site-packages\\requests-2.32.5.dist-info', 'requests-2.32.5.dist-info'), ('C:\\Users\\leoma\\AppData\\Local\\Programs\\Python\\Python312\\Lib\\site-packages\\pydeck-0.9.1.dist-info', 'pydeck-0.9.1.dist-info'), ('C:\\Users\\leoma\\AppData\\Local\\Programs\\Python\\Python312\\Lib\\site-packages\\watchdog-6.0.0.dist-info', 'watchdog-6.0.0.dist-info'), ('C:\\Users\\leoma\\AppData\\Local\\Programs\\Python\\Python312\\Lib\\site-packages\\gitpython-3.1.46.dist-info', 'gitpython-3.1.46.dist-info'), ('C:\\Users\\leoma\\AppData\\Local\\Programs\\Python\\Python312\\Lib\\site-packages\\blinker-1.9.0.dist-info', 'blinker-1.9.0.dist-info'), ('C:\\Users\\leoma\\AppData\\Local\\Programs\\Python\\Python312\\Lib\\site-packages\\cachetools-6.2.6.dist-info', 'cachetools-6.2.6.dist-info'), ('C:\\Users\\leoma\\AppData\\Local\\Programs\\Python\\Python312\\Lib\\site-packages\\rich-13.9.4.dist-info', 'rich-13.9.4.dist-info'), ('C:\\Users\\leoma\\AppData\\Local\\Programs\\Python\\Python312\\Lib\\site-packages\\tenacity-9.1.4.dist-info', 'tenacity-9.1.4.dist-info'), ('C:\\Users\\leoma\\AppData\\Local\\Programs\\Python\\Python312\\Lib\\site-packages\\typing_extensions-4.15.0.dist-info', 'typing_extensions-4.15.0.dist-info'), ('C:\\Users\\leoma\\AppData\\Local\\Programs\\Python\\Python312\\Lib\\site-packages\\markupsafe-3.0.3.dist-info', 'markupsafe-3.0.3.dist-info'), ('C:\\Users\\leoma\\AppData\\Local\\Programs\\Python\\Python312\\Lib\\site-packages\\charset_normalizer-3.4.4.dist-info', 'charset_normalizer-3.4.4.dist-info'), ('C:\\Users\\leoma\\AppData\\Local\\Programs\\Python\\Python312\\Lib\\site-packages\\certifi-2025.10.5.dist-info', 'certifi-2025.10.5.dist-info'), ('C:\\Users\\leoma\\AppData\\Local\\Programs\\Python\\Python312\\Lib\\site-packages\\urllib3-2.5.0.dist-info', 'urllib3-2.5.0.dist-info'), ('C:\\Users\\leoma\\AppData\\Local\\Programs\\Python\\Python312\\Lib\\site-packages\\idna-3.11.dist-info', 'idna-3.11.dist-info'), ('C:\\Users\\leoma\\AppData\\Local\\Programs\\Python\\Python312\\Lib\\site-packages\\attrs-25.4.0.dist-info', 'attrs-25.4.0.dist-info'), ('C:\\Users\\leoma\\AppData\\Local\\Programs\\Python\\Python312\\Lib\\site-packages\\jsonschema-4.26.0.dist-info', 'jsonschema-4.26.0.dist-info'), ('C:\\Users\\leoma\\AppData\\Local\\Programs\\Python\\Python312\\Lib\\site-packages\\jsonschema_specifications-2025.9.1.dist-info', 'jsonschema_specifications-2025.9.1.dist-info'), ('C:\\Users\\leoma\\AppData\\Local\\Programs\\Python\\Python312\\Lib\\site-packages\\referencing-0.37.0.dist-info', 'referencing-0.37.0.dist-info'), ('C:\\Users\\leoma\\AppData\\Local\\Programs\\Python\\Python312\\Lib\\site-packages\\rpds_py-0.30.0.dist-info', 'rpds_py-0.30.0.dist-info'), ('C:\\Users\\leoma\\AppData\\Local\\Programs\\Python\\Python312\\Lib\\site-packages\\narwhals-2.17.0.dist-info', 'narwhals-2.17.0.dist-info'), ('C:\\Users\\leoma\\AppData\\Local\\Programs\\Python\\Python312\\Lib\\site-packages\\pyarrow', 'pyarrow')],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='ART_Check',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
