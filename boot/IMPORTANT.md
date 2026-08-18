# 重要：boot/boot.img 不要直接 fastboot flash！

`boot/boot.img`（48MB，kernel-only）是早期版本，fastboot 写入时会**覆盖原 boot 分区里的 vbmeta 段**（vbmeta 在 offset 0x29ee000 处，48MB 写入会覆盖到 offset 0x3000000 包含整个 vbmeta 段），bootloader 找不到 vbmeta 直接回 fastboot 开不了机。

## 正确做法

下载并刷入以下 128MB 修复版 boot.img：

- **`boot/stock_boot_conservative_vbmeta.bin`**（保守版，**推荐默认**）：Docker 内核 + 完整保留 vbmeta
  - 下载: `https://raw.githubusercontent.com/huliaiya/boot/main/boot/stock_boot_conservative_vbmeta.bin`
- **`boot/stock_boot_full_vbmeta.bin`**（激进版）：完整 Docker 特性（含 USER_NS、NF_TABLES）
  - 下载: `https://raw.githubusercontent.com/huliaiya/boot/main/boot/stock_boot_full_vbmeta.bin`
- **`boot/stock_boot_stripped.bin`**（fallback）：vbmeta 段清空
  - 下载: `https://raw.githubusercontent.com/huliaiya/boot/main/boot/stock_boot_stripped.bin`
- **`boot/stock_boot.bin`**（救机）：原版 boot 分区 dump
  - 下载: `https://raw.githubusercontent.com/huliaiya/boot/main/boot/stock_boot.bin`

## 刷机命令

```bash
# 保守版（先试这个）
fastboot flash boot stock_boot_conservative_vbmeta.bin
fastboot reboot

# 激进版（保守版不开机时）
fastboot flash boot stock_boot_full_vbmeta.bin
fastboot reboot

# stripped（仍不开机）
fastboot flash boot stock_boot_stripped.bin
fastboot reboot

# 救机（任何情况都能恢复）
fastboot flash boot stock_boot.bin
fastboot reboot
```

## 为什么 128MB

K20 Pro boot 分区实际大小 128MB。结构：

```
[0x00000000 - 0x00001000] header (4KB)
[0x00001000 - 0x0x29ee000] kernel (~44MB)
[0x029ee000 - 0x02d6e000] vbmeta (3.5MB)
[0x02d6e000 - 0x07ffffc0] padding
[0x07ffffc0 - 0x07fffffe] vbmeta footer (64B)
```

只刷 48MB 会破坏 vbmeta 段。修复版整体保持 128MB，把 kernel 替换为 Docker 内核，vbmeta 段完整保留并挪到新 offset。
