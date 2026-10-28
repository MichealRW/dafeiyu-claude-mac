# Build from any checkout: python -m PyInstaller --noconfirm app.spec
from pathlib import Path
ROOT=Path(SPECPATH)
a=Analysis([str(ROOT/'main.py')],pathex=[str(ROOT)],
    datas=[(str(ROOT/name),name) for name in ['sprites','animations','assets']]
        +[(str(ROOT/name),'.') for name in ['LICENSE','LICENSE.upstream','NOTICE.txt','ANIMATION_ATTRIBUTION.md','ASSET_LICENSE.md']],
    binaries=[],hiddenimports=[],hookspath=[],hooksconfig={},runtime_hooks=[],
    excludes=[],noarchive=False,optimize=0)
pyz=PYZ(a.pure)
exe=EXE(pyz,a.scripts,[],exclude_binaries=True,name='大肥鱼桌宠',
    debug=False,bootloader_ignore_signals=False,strip=False,upx=False,console=False,
    disable_windowed_traceback=False,argv_emulation=False,target_arch=None,
    codesign_identity=None,entitlements_file=None)
coll=COLLECT(exe,a.binaries,a.datas,strip=False,upx=False,name='大肥鱼桌宠')
app=BUNDLE(coll,name='大肥鱼桌宠.app',icon=str(ROOT/'assets/AppIcon.icns'),
    bundle_identifier='local.dafeiyu.claude',
    info_plist={'LSUIElement':True,'CFBundleDisplayName':'大肥鱼桌宠',
        'CFBundleShortVersionString':'1.2.0','NSHighResolutionCapable':True})
