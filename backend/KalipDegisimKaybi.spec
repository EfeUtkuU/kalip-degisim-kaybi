# -*- mode: python ; coding: utf-8 -*-
# PyInstaller tarifi: build_macos_app.sh tarafından çalıştırılır.
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

hidden = collect_submodules("uvicorn") + collect_submodules("scipy.optimize") + [
    "scipy.special._cdflib", "openpyxl",
    "multipart", "python_multipart",
]
datas = [("frontend_dist", "frontend_dist")] + collect_data_files("webview")

a = Analysis(["desktop_launcher.py"], pathex=["."], datas=datas, hiddenimports=hidden, excludes=["tkinter", "matplotlib", "IPython", "pytest"])
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="KalipDegisimKaybi", console=False)
coll = COLLECT(exe, a.binaries, a.datas, name="KalipDegisimKaybi")
app = BUNDLE(coll, name="KalipDegisimKaybi.app", icon="icon.icns", bundle_identifier="com.kalip.degisimkaybi",
             info_plist={"CFBundleName": "Kalıp Değişim Kaybı", "CFBundleDisplayName": "Kalıp Değişim Kaybı", "NSHighResolutionCapable": True,
                         "CFBundleShortVersionString": "1.0.0"})
