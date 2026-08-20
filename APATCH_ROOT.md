# APatch Root 流程 (K20 Pro, 保留 vbmeta)

## 问题背景

小米 K20 Pro boot 分区 128MB，结构：

```
[0..0x1000]      header (4KB)
[0x1000..kernel_end] kernel (~46MB)
[vbmeta_offset..vbmeta_offset+3.5MB] vbmeta (AVB0 magic)
[file_end-64..file_end] vbmeta footer (AVBf)
```

APatch/KernelPatch 0.13.x 的 `kptools repack` 修补 boot.img 时会**破坏 vbmeta 段**：

- vbmeta 段 3.5MB 中**只有前 848 字节有真实数据**，其余全是 0 (小米 ROM 设计)
- kptools 把 vbmeta 段当成"稀疏数据"，只保留前 848 字节，其余当 padding 丢了
- 修补后的 patched_boot.img vbmeta 段不完整，bootloader AVB 验证失败
- fastboot flash boot patched_boot.img → 开不了机进 fastboot

## 解决

`build_patched_bootimg.py` 修复 vbmeta 段保留问题：

- 强制按固定 3.5MB 大小保留 vbmeta 段
- 不依赖 footer 字段含义（小米魔改 AVB footer 字段不可靠）
- 替换 kernel 段，挪 vbmeta 到新 offset，更新 footer

## 使用流程

### 步骤 1：先刷修复版 boot.img 验证内核能启动

```bash
# 下载修复版 (保守 Docker 内核 + 保留 vbmeta)
curl -L -o boot_docker.bin \
  https://raw.githubusercontent.com/huliaiya/boot/main/boot/stock_boot_conservative_vbmeta.bin

# 刷入
adb reboot bootloader
fastboot flash boot boot_docker.bin
fastboot reboot
```

确认能进系统后继续。

### 步骤 2：在手机上用 APatch 应用修补 boot.img

1. 安装 APatch 0.13.x 应用 (APatch 官网或酷安)
2. 打开 APatch → 修补内核/修补 Boot 镜像
3. 选择从电脑 push 进去的 `boot_docker.bin`（修复版 boot.img）
4. 点击"开始修补"
5. APatch 输出 patched boot.img 到 `/data/adb/apatch/` 下（具体路径看 APatch 提示）
6. 通过 adb pull 到电脑：
   ```bash
   adb pull /data/adb/apatch/<patched-file> ./patched_boot_from_apatch.img
   ```

**重要**：APatch 输出文件本身 vbmeta 段已损坏，但 kernel 段包含 APatch 修补（kpatch + kernelpatch.ko 嵌入）。我们只需要从中提取**修补过的 kernel**。

### 步骤 3：从 APatch 输出提取修补过的 kernel

在电脑上：

```bash
# 安装 kptools (KernelPatch 工具, 用于 unpack)
# 从 https://github.com/bmax121/KernelPatch/releases 下载 linux-aarch64.tar.gz
# 或用 apt 装 (Debian/Ubuntu):
# sudo apt install libavb-tools

# 用 kptools 解包 APatch 输出
kptools unpack patched_boot_from_apatch.img -o patched_kernel.img
```

### 步骤 4：用脚本重新打包，保留 vbmeta

```bash
python3 build_patched_bootimg.py \
  --orig boot_docker.bin \
  --new-kernel patched_kernel.img \
  --out boot_rooted.bin
```

`boot_rooted.bin` 是修补过的、保留 vbmeta 的 boot.img。

### 步骤 5：刷入修补过的 boot.img

```bash
adb reboot bootloader
fastboot flash boot boot_rooted.bin
fastboot reboot
```

启动后 APatch 应该自动激活（kernel 加载时启动 kernelpatch.ko）。

## 备选方案：在 PC 上用 kptools + 脚本做完整修补

如果有 KP 的 kpimg 文件（KernelPatch 项目产物），可以直接在 PC 上：

```bash
# 1. 解包修复版 boot.img
kptools unpack boot_docker.bin -o kernel.img

# 2. 用 kpimg 修补 kernel
kptools -p -i kernel.img -k /path/to/kpimg.img -o patched_kernel.img

# 3. 用脚本重新打包 (保留 vbmeta)
python3 build_patched_bootimg.py \
  --orig boot_docker.bin \
  --new-kernel patched_kernel.img \
  --out boot_rooted.bin
```

## 救机

任何时候救机回到原版 boot 分区：

```bash
curl -L -o boot_stock.bin \
  https://raw.githubusercontent.com/huliaiya/boot/main/boot/stock_boot.bin
adb reboot bootloader
fastboot flash boot boot_stock.bin
fastboot reboot
```

## 参考

- KernelPatch 项目: https://github.com/bmax121/KernelPatch
- APatch 项目: https://github.com/bmax121/APatch
- AVB 规范: https://android.googlesource.com/platform/external/avb/+/master
