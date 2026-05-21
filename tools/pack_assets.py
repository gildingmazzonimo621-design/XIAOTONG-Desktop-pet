#!/usr/bin/env python3
"""
动画资源打包工具  ——  仅供开发者使用，不随发布包分发
========================================================
功能：
  1. 将 assets/animations/*.png 序列帧缩小至 512×512 并打包成 .pak
  2. 将 assets/items/*.png 序列帧缩小至 320×320 并打包成 .pak
  3. 写完后询问是否删除原始 PNG（保留原图时两者共存，加载器优先 .pak）

用法：
  python tools/pack_assets.py              # 交互模式，询问是否删原图
  python tools/pack_assets.py --keep-png  # 静默模式，保留原始 PNG
  python tools/pack_assets.py --del-png   # 静默模式，删除原始 PNG

后续新增动作：
  把新动作的 PNG 序列帧放入对应目录，再次运行此脚本即可打包新动作。
  已存在的 .pak 不会被重新打包（除非使用 --force 参数覆盖）。
"""
from __future__ import annotations

import argparse
import io
import json
import os
import sys
import zipfile

# ── 路径设置 ─────────────────────────────────────────────────────────────────
_SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
_ROOT        = os.path.dirname(_SCRIPT_DIR)
_ANIM_DIR    = os.path.join(_ROOT, "assets", "animations")
_ITEM_DIR    = os.path.join(_ROOT, "assets", "items")
sys.path.insert(0, _ROOT)

from src.pak_loader import obfuscate   # noqa: E402  (需要 sys.path 先设好)

try:
    from PIL import Image
except ImportError:
    print("[错误] 缺少 Pillow 库。请先运行: pip install pillow")
    sys.exit(1)

# ── 目标分辨率 ────────────────────────────────────────────────────────────────
ANIM_SIZE = 512   # 主动画帧（原1920×1920），比显示尺寸大1.5倍保留清晰度
ITEM_SIZE = 320   # 道具帧（原已是320×320，不放大）

# ── 工具函数 ─────────────────────────────────────────────────────────────────

def _collect_frames(directory: str, prefix: str) -> list[str]:
    """按帧序号顺序收集 prefix_XXXX.png 文件路径"""
    frames: list[str] = []
    i = 0
    while True:
        path = os.path.join(directory, f"{prefix}_{i:04d}.png")
        if not os.path.exists(path):
            break
        frames.append(path)
        i += 1
    return frames


def _detect_actions(directory: str) -> list[str]:
    """扫描目录，找出所有有序列帧的动作前缀"""
    seen: set[str] = set()
    actions: list[str] = []
    for fname in sorted(os.listdir(directory)):
        if not fname.endswith(".png"):
            continue
        # 格式: prefix_XXXX.png
        parts = fname[:-4].rsplit("_", 1)
        if len(parts) == 2 and parts[1].isdigit() and len(parts[1]) == 4:
            prefix = parts[0]
            if prefix not in seen:
                seen.add(prefix)
                actions.append(prefix)
    return actions


def pack_action(frames: list[str], out_path: str,
                target_size: int, force: bool = False) -> bool:
    """
    将帧序列打包成 .pak 文件。
    返回 True 表示本次执行了打包，False 表示已存在且跳过。
    """
    if os.path.exists(out_path) and not force:
        print(f"  [OK] 已存在，跳过  ->  {os.path.basename(out_path)}")
        return False

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for idx, png_path in enumerate(frames):
            img = Image.open(png_path).convert("RGBA")
            # 只缩小，不放大（道具原图已是320，不需要放大）
            if img.width > target_size or img.height > target_size:
                img = img.resize((target_size, target_size), Image.LANCZOS)
            frame_buf = io.BytesIO()
            img.save(frame_buf, "PNG", optimize=True)
            zf.writestr(f"{idx:04d}.png", frame_buf.getvalue())

    raw_zip  = buf.getvalue()
    pak_data = obfuscate(raw_zip)

    with open(out_path, "wb") as f:
        f.write(pak_data)

    orig_mb = sum(os.path.getsize(p) for p in frames) / 1024 / 1024
    pak_mb  = len(pak_data) / 1024 / 1024
    ratio   = (1 - pak_mb / orig_mb) * 100 if orig_mb > 0 else 0
    print(f"  [OK] {len(frames):3d}f  {orig_mb:6.1f}MB -> {pak_mb:5.1f}MB  "
          f"(-{ratio:.0f}%)  ->  {os.path.basename(out_path)}")
    return True


def delete_pngs(frames: list[str]):
    for p in frames:
        try:
            os.remove(p)
        except OSError as e:
            print(f"  [WARN] delete failed: {p} ({e})")


# ── 主流程 ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Desktop Pet - Animation Packer")
    grp = parser.add_mutually_exclusive_group()
    grp.add_argument("--keep-png", action="store_true", help="keep original PNG files")
    grp.add_argument("--del-png",  action="store_true", help="delete PNGs after packing")
    parser.add_argument("--force", action="store_true",
                        help="re-pack even if .pak already exists")
    args = parser.parse_args()

    print("=" * 60)
    print("  Desktop Pet - Animation Packer")
    print("=" * 60)

    packed_frames: dict[str, list[str]] = {}   # out_path -> frame list（用于后续删除）
    total_packed = 0

    # ── 打包主动画 ──────────────────────────────────────────────────
    print(f"\n[main anim]  target {ANIM_SIZE}x{ANIM_SIZE}  ({_ANIM_DIR})")
    anim_actions = _detect_actions(_ANIM_DIR)
    for action in anim_actions:
        frames = _collect_frames(_ANIM_DIR, action)
        if not frames:
            continue
        out_path = os.path.join(_ANIM_DIR, f"{action}.pak")
        did_pack = pack_action(frames, out_path, ANIM_SIZE, force=args.force)
        if did_pack or os.path.exists(out_path):
            packed_frames[out_path] = frames
            if did_pack:
                total_packed += 1

    # ── 打包道具动画 ────────────────────────────────────────────────
    print(f"\n[items]  target {ITEM_SIZE}x{ITEM_SIZE}  ({_ITEM_DIR})")
    item_actions = _detect_actions(_ITEM_DIR)
    for action in item_actions:
        frames = _collect_frames(_ITEM_DIR, action)
        if not frames:
            continue
        out_path = os.path.join(_ITEM_DIR, f"{action}.pak")
        did_pack = pack_action(frames, out_path, ITEM_SIZE, force=args.force)
        if did_pack or os.path.exists(out_path):
            packed_frames[out_path] = frames
            if did_pack:
                total_packed += 1

    print(f"\nPacked {total_packed} action(s) this run.")

    # ── 询问是否删除原始 PNG ────────────────────────────────────────
    all_frames_to_del = [f for frames in packed_frames.values() for f in frames]
    png_exist = [f for f in all_frames_to_del if os.path.exists(f)]

    if not png_exist:
        print("No original PNGs found, nothing to delete.")
        print("\nDone!")
        return

    if args.keep_png:
        do_del = False
    elif args.del_png:
        do_del = True
    else:
        print(f"\nFound {len(png_exist)} original PNG files.")
        ans = input("Delete original PNGs? (y/N): ").strip().lower()
        do_del = ans == "y"

    if do_del:
        print("Deleting original PNGs...")
        delete_pngs(png_exist)
        print(f"Deleted {len(png_exist)} files.")
    else:
        print("Kept original PNGs. (loader will prefer .pak at runtime)")

    print("\nDone!")
    print("Tip: distribute only .pak files, no original PNGs needed.")


if __name__ == "__main__":
    main()
