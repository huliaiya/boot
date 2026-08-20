#!/usr/bin/env python3
"""
build_patched_bootimg.py - 构造修补过的 boot.img (保留 vbmeta 段)

支持小米 K20 Pro 风格的 boot.img 结构 (实测):
  [0x0     - 0x1000] header (4KB)
  [0x1000  - kernel_end] kernel
  [vbmeta_offset..file_end-64) vbmeta (AVB0, 实际数据稀疏)
  [file_end - 64, file_end) vbmeta footer (AVBf magic)

实测小米 AVB footer 字段布局 (BE uint32):
  0-3:   magic "AVBf"
  4-7:   version (uint32 BE) = 1
  8-15:  ? (一般全 0)
  16-23: vbmeta_offset (uint64 BE) = 0x29ee000
  24-31: ? (未知字段)
  32-39: ? (未知字段)
  40-63: salt (zeros)

注: vbmeta 段真实大小 = file_size - 64 - vbmeta_offset
"""

import struct
import sys
import argparse
import hashlib


def parse_vbmeta_footer(data):
    """解析 64 字节 vbmeta footer (BE uint32 字段)"""
    if data[:4] != b'AVBf':
        raise ValueError(f"末尾 64 字节不是 AVBf footer (magic={data[:4]})")
    version = struct.unpack('>I', data[4:8])[0]
    vbmeta_offset_lo = struct.unpack('>I', data[16:20])[0]
    vbmeta_offset_hi = struct.unpack('>I', data[20:24])[0]
    vbmeta_offset = (vbmeta_offset_hi << 32) | vbmeta_offset_lo

    return {
        'magic': data[:4],
        'version': version,
        'vbmeta_offset': vbmeta_offset,
    }


def parse_header(data):
    """解析 Android boot image header (v0/v1)"""
    if data[:8] != b'ANDROID!':
        raise ValueError("Not an Android boot image (magic mismatch)")
    return {
        'kernel_size': struct.unpack('<I', data[8:12])[0],
        'page_size': struct.unpack('<I', data[36:40])[0],
        'ramdisk_size': struct.unpack('<I', data[24:28])[0],
    }


def build_patched_bootimg(orig_data, new_kernel, partition_size=None):
    """构造修补过的 boot.img, 保留 vbmeta 段"""
    hdr = parse_header(orig_data[:0x1000])
    print(f"[+] 原 header: kernel_size={hdr['kernel_size']} page_size={hdr['page_size']}")

    footer_data = orig_data[-64:]
    ftr = parse_vbmeta_footer(footer_data)
    print(f"[+] 原 vbmeta footer:")
    print(f"    version: {ftr['version']}")
    print(f"    vbmeta_offset: {ftr['vbmeta_offset']:#x}")

    vbmeta_offset = ftr['vbmeta_offset']
    if vbmeta_offset == 0:
        raise ValueError(f"vbmeta_offset 无效")

    # 小米 K20 Pro 实测: vbmeta 段固定大小 3.5MB (0x380000)
    # footer 字段不可靠，直接用固定大小
    vbmeta_size = 0x380000
    print(f"[+] vbmeta 段固定大小 (小米 ROM): {vbmeta_size} bytes ({vbmeta_size / 1024 / 1024:.1f} MB)")

    vbmeta = orig_data[vbmeta_offset:vbmeta_offset + vbmeta_size]
    print(f"[+] vbmeta sha256: {hashlib.sha256(vbmeta).hexdigest()}")

    if partition_size is None:
        partition_size = len(orig_data)
    if partition_size < 0x1000 + len(new_kernel) + vbmeta_size + 64:
        raise ValueError(f"partition_size {partition_size} 太小")

    page_size = hdr['page_size']
    new_kernel_aligned = (len(new_kernel) + page_size - 1) & ~(page_size - 1)
    new_vbmeta_offset = 0x1000 + new_kernel_aligned
    print(f"[+] 新 kernel: {len(new_kernel)} bytes")
    print(f"[+] 新 vbmeta offset: {new_vbmeta_offset:#x}")

    new_header = bytearray(orig_data[:0x1000])
    struct.pack_into('<I', new_header, 8, len(new_kernel))

    new_footer = bytearray(footer_data)
    struct.pack_into('>I', new_footer, 16, new_vbmeta_offset & 0xffffffff)
    struct.pack_into('>I', new_footer, 20, (new_vbmeta_offset >> 32) & 0xffffffff)

    out = bytearray(partition_size)
    out[0:0x1000] = new_header
    out[0x1000:0x1000 + len(new_kernel)] = new_kernel
    out[new_vbmeta_offset:new_vbmeta_offset + vbmeta_size] = vbmeta
    out[partition_size - 64:partition_size] = new_footer

    print(f"[+] 输出大小: {partition_size}")
    print(f"[+] boot.img sha256: {hashlib.sha256(bytes(out)).hexdigest()}")
    return bytes(out)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--orig', required=True, help='原 boot.img (含 vbmeta)')
    p.add_argument('--new-kernel', required=True, help='新 kernel (Image 格式)')
    p.add_argument('--out', required=True, help='输出 boot.img')
    p.add_argument('--partition-size', type=int, default=0, help='输出大小 (默认与原相同)')
    args = p.parse_args()

    with open(args.orig, 'rb') as f:
        orig = f.read()
    with open(args.new_kernel, 'rb') as f:
        new_kernel = f.read()

    partition_size = args.partition_size or len(orig)
    print(f"[+] 原: {args.orig} ({len(orig)} bytes)")
    print(f"[+] 新 kernel: {args.new_kernel} ({len(new_kernel)} bytes)")
    print(f"[+] 输出: {partition_size} bytes")

    out = build_patched_bootimg(orig, new_kernel, partition_size)
    with open(args.out, 'wb') as f:
        f.write(out)
    print(f"[+] 保存到 {args.out}")


if __name__ == '__main__':
    main()
