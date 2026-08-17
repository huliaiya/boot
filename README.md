# boot

红米 K20 Pro / Mi 9T Pro（骁龙855，raphael）Docker 定制内核。

- 内核版本：`4.14.246-K20Pro-Docker`（arm64，SMP PREEMPT）
- 基础源码：CAF 4.14.246 for Xiaomi SM8150（Immensity，android11 分支）
- 工具链：Proton clang 13.0.0 (LLD 13.0.0)
- 在 `raphael_defconfig` 基础上补齐 Docker 所需内核特性（PID/USER/IPC 命名空间、cgroup device/pids、OverlayFS、VETH、bridge-nf、nftables、NAT、IPVS、xt_addrtype 等）

## 文件

| 文件 | 说明 |
|---|---|
| `boot/boot.img` | 编译好的 boot 镜像（含内核，无 ramdisk），直接刷入 |
| `docker_fragment.config` | 新增的 Docker 特性配置片段 |
| `DOCKER_KERNEL_USAGE.md` | 完整使用说明（刷入 / chroot / Docker 安装与启动） |

## 快速开始

1. 用 Kernel Flasher / TWRP / fastboot 刷入 `boot/boot.img`
2. 在 chroot 的 `/sys/fs/cgroup` 挂载 cgroup（详见使用说明第三节）
3. 安装 Docker（aarch64 静态包或 apt），运行 `containerd &` + `dockerd &`
4. `docker run hello-world` 验证

详见 [DOCKER_KERNEL_USAGE.md](DOCKER_KERNEL_USAGE.md)。
