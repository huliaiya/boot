# boot

红米 K20 Pro / Mi 9T Pro（骁龙855，raphael）Docker 定制内核。

- 内核版本：`4.14.246-K20Pro-Docker`（arm64，SMP PREEMPT）
- 基础源码：CAF 4.14.246 for Xiaomi SM8150（Immensity，android11 分支）
- 工具链：Proton clang 13.0.0 (LLD 13.0.0)
- 在 `raphael_defconfig` 基础上补齐 Docker 所需内核特性（命名空间、cgroup device/pids、OverlayFS、VETH、bridge-nf、iptables、NAT、IPVS、xt_addrtype 等）

## 两个版本

| 版本 | 配置 | Image | 推荐场景 |
|---|---|---|---|
| 激进版 | `docker_fragment.config` | 48.7MB | 完整 Docker 特性（USER_NS、nftables、checkpoint） |
| **保守版** | `docker_fragment_conservative.config` | 46.4MB | **默认推荐**：关 USER_NS（防银行 App 检测）、关 NF_TABLES（用 iptables-legacy 兼容 Android 网络栈）、关 CHECKPOINT_RESTORE（Android 不用） |

保守版牺牲的 Docker 功能（一般用不到）：
- `--userns-remap`（命名空间用户映射）
- `nftables` 后端（Docker daemon 默认 iptables 即可）

## 文件

| 文件 | 说明 |
|---|---|
| `boot/stock_boot_conservative_vbmeta.bin` | **推荐**：128MB 修复版 boot.img（保守版内核 + 保留 vbmeta） |
| `boot/stock_boot_full_vbmeta.bin` | 128MB 修复版 boot.img（激进版内核 + 保留 vbmeta） |
| `boot/stock_boot_stripped.bin` | 128MB fallback：vbmeta 段清空 |
| `boot/stock_boot.bin` | 128MB 原版 boot.img dump，纯刷回救机用 |
| `boot/boot.img` (LFS) | 早期 48MB kernel-only boot.img，**不要直接 fastboot flash boot**（覆盖 vbmeta 段导致开不了机） |
| `docker_fragment_conservative.config` | 保守版 Docker 特性配置片段 |
| `docker_fragment.config` | 激进版 Docker 特性配置片段 |
| `DOCKER_KERNEL_USAGE.md` | 完整使用说明（刷入 / chroot / Docker 安装与启动） |

## 快速开始（修复版 boot.img）

```bash
# 1. 下载保守版修复版（推荐）
curl -L -o boot_docker.bin \
  https://raw.githubusercontent.com/huliaiya/boot/main/boot/stock_boot_conservative_vbmeta.bin

# 2. 进入 fastboot 模式，刷入
adb reboot bootloader
fastboot flash boot boot_docker.bin
fastboot reboot
```

如果刷入后仍直接进 fastboot：

```bash
# 退回 stripped 版（清空 vbmeta 段）
curl -L -o boot_docker_stripped.bin \
  https://raw.githubusercontent.com/huliaiya/boot/main/boot/stock_boot_stripped.bin
fastboot flash boot boot_docker_stripped.bin
fastboot reboot
```

如果仍不开机，刷回原版：

```bash
curl -L -o boot_stock.bin \
  https://raw.githubusercontent.com/huliaiya/boot/main/boot/stock_boot.bin
fastboot flash boot boot_stock.bin
fastboot reboot
```

## 刷机后续（启用 Docker 内核）

1. 在 chroot 的 `/sys/fs/cgroup` 挂载 cgroup（详见使用说明第三节）
2. 安装 Docker（aarch64 静态包或 apt），运行 `containerd &` + `dockerd &`
3. `docker run hello-world` 验证

详见 [DOCKER_KERNEL_USAGE.md](DOCKER_KERNEL_USAGE.md)。

## 之前刷 48MB boot.img 开不了机的原因

仓库里早期 `boot/boot.img` 只有 48MB（kernel-only），fastboot 写入时直接覆盖原 128MB boot 分区的前 48MB，把 vbmeta 段（offset 0x29ee000 = 44MB 处）彻底破坏了，bootloader 找不到有效 vbmeta 拒绝启动并回落 fastboot——跟内核本身能不能跑无关。修复版把 vbmeta 段完整保留并后移到新 offset。
