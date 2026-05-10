"""
.pak 资源包读写模块
---------------------
.pak = 魔数头(8字节) + XOR混淆后的ZIP数据

目的：防止用户直接改扩展名打开查看原始帧图像。
     不是加密，是轻量混淆；开发者工具链（pack_assets.py）可完整还原。
"""
from __future__ import annotations

import io
import zipfile

# ── 混淆参数（修改后需重新打包所有 .pak）────────────────────────────────────
_MAGIC   = b'PTPAK\x01\x00\x00'          # 8 字节文件头标识
_XOR_KEY = b'\x54\x6f\x6e\x67\x50\x65\x74\x41\x6e\x69\x6d'   # "TongPetAnim"
# ────────────────────────────────────────────────────────────────────────────


def _xor(data: bytes) -> bytes:
    """XOR 混淆/还原（大整数运算，C 速度，比逐字节循环快 ~17x）"""
    if not data:
        return b''
    key  = _XOR_KEY
    klen = len(key)
    n    = len(data)
    full_key = (key * (n // klen + 1))[:n]
    result = int.from_bytes(data, 'little') ^ int.from_bytes(full_key, 'little')
    return result.to_bytes(n, 'little')


def obfuscate(raw_zip: bytes) -> bytes:
    """将 ZIP 字节流混淆为 .pak 格式（打包时调用）"""
    return _MAGIC + _xor(raw_zip)


def deobfuscate(pak_data: bytes) -> bytes:
    """将 .pak 字节流还原为 ZIP 字节流（运行时调用）"""
    mlen = len(_MAGIC)
    if pak_data[:mlen] != _MAGIC:
        raise ValueError("不是有效的 .pak 文件（魔数不匹配）")
    return _xor(pak_data[mlen:])


def open_pak(path: str) -> zipfile.ZipFile:
    """
    打开一个 .pak 文件，返回可读取内部帧的 ZipFile 对象。
    调用方负责 close()，或使用 with 语句。
    """
    with open(path, "rb") as f:
        raw = f.read()
    zip_bytes = deobfuscate(raw)
    return zipfile.ZipFile(io.BytesIO(zip_bytes), "r")


def read_frame_bytes(zf: zipfile.ZipFile, idx: int) -> bytes | None:
    """从已打开的 ZipFile 读取第 idx 帧的 PNG 字节，不存在则返回 None"""
    name = f"{idx:04d}.png"
    try:
        return zf.read(name)
    except KeyError:
        return None
