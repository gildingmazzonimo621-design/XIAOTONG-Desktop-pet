# -*- mode: python ; coding: utf-8 -*-
"""
蓝色小嗵 打包配置
运行方式: python -m PyInstaller build.spec
输出目录: dist/xiaotong/
"""

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        # 动画资源包
        ('assets/animations', 'assets/animations'),
        ('assets/items',      'assets/items'),
        # 内置角色设定
        ('data/default_persona.txt', 'data'),
        # 图标
        ('icons', 'icons'),
        # 赞赏码
        ('shoukuanma.jpg', '.'),
    ],
    hiddenimports=[
        'PyQt5.QtCore',
        'PyQt5.QtGui',
        'PyQt5.QtWidgets',
        'PyQt5.sip',
        'src.pak_loader',
        'src.pet_renderer_sprite',
        'src.pet_animator',
        'src.pet_state',
        'src.chat_service',
        'src.status_panel',
        'src.knowledge_hub',
        'src.game_systems',
        'src.bubble_widget',
        'src.input_monitor',
        'src.web_crawler',
        'src.user_data',
        'src.snap_system',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter', 'matplotlib', 'numpy', 'scipy',
        'PIL', 'cv2', 'test', 'unittest',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='xiaotong',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,          # 不显示黑色命令行窗口
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='icons/icon.ico',  # exe 图标
    manifest='tools/dpi_aware.manifest',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='xiaotong',
    contents_directory='.',  # 所有文件平铺在 exe 旁边，不进 _internal 子目录
)
