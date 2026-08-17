# K20Pro Docker 定制内核 · 使用说明

本仓库的 `boot/boot.img` 是为 **红米 K20 Pro / Mi 9T Pro（骁龙855，代号 raphael）** 重新编译的内核镜像，版本为 `4.14.246-K20Pro-Docker`。它在原版 4.14.180 内核基础上补齐了运行 Docker / 容器所需的所有内核特性，**在 Android 系统的 chroot 环境里可以直接跑最新版 Docker**。

---

## 一、文件说明

| 文件 | 说明 |
|---|---|
| `boot/boot.img` | 新内核 boot 镜像（48.7MB），刷入这个即可 |
| `docker_fragment.config` | 本次为内核新增的 Docker 特性配置片段（用于复现构建） |

> 该镜像与官方 boot.img 一样**只含内核、不含 ramdisk**，刷入时工具会保留你 ROM 自带的 ramdisk。

---

## 二、刷入方法（任选一种）

> 刷机有风险，操作前请**先备份当前 boot 分区**。本内核基于 Android 11 (MIUI 12/12.5) 及以上的 raphael 内核分支构建，请确认你的 ROM 版本。

### 方法 A：Kernel Flasher（推荐，最简单）

1. 把 `boot/boot.img` 传到手机
2. 安装 **Kernel Flasher**（Google Play 或 FKM / EXKM 均可）
3. 打开 App → 选择 "Flash a kernel" → 选中 `boot.img`
4. 确认后刷入，重启

### 方法 B：TWRP 刷入

1. 把 `boot/boot.img` 传到手机
2. 重启进 TWRP → Install → 右下角切换为 "Install Image"
3. 选中 `boot.img` → 分区选择 **Boot**
4. Swipe 确认刷入，重启

### 方法 C：fastboot 刷入（需已解锁 BL）

```bash
adb reboot bootloader
fastboot flash boot boot.img
fastboot reboot
```

### 刷入后验证

```bash
# 手机终端（Termux 或 adb shell）
uname -r
# 应显示: 4.14.246-K20Pro-Docker
```

---

## 三、准备 chroot 环境

> 以下假设你有一个 Linux rootfs（Debian/Ubuntu 等，aarch64），放在 `/data/local/rootfs`。
> 没有的话可以用 `proot`/`debootstrap` 生成一个，或使用 Termux 的 proot-distro。

先在宿主（Termux root / adb shell root）里挂载 chroot 需要的虚拟文件系统：

```bash
# 假设 rootfs 位于 /data/local/rootfs
export ROOTFS=/data/local/rootfs

mkdir -p $ROOTFS/{proc,sys,dev,tmp}

mount -t proc     proc     $ROOTFS/proc
mount -t sysfs    sysfs    $ROOTFS/sys
mount -t tmpfs    tmpfs    $ROOTFS/dev
mkdir -p $ROOTFS/dev/pts
mount -t devpts   devpts   $ROOTFS/dev/pts
```

**关键：挂载 cgroup**（Docker 启动必需，省略这一步 `dockerd` 会直接报错退出）。挂载位置就是 chroot 根目录下的 `/sys/fs/cgroup`，即宿主机上的 `$ROOTFS/sys/fs/cgroup`：

```bash
mkdir -p $ROOTFS/sys/fs/cgroup
mount -t tmpfs tmpfs $ROOTFS/sys/fs/cgroup

for c in blkio cpu cpuacct cpuset devices freezer memory pids; do
  mkdir -p $ROOTFS/sys/fs/cgroup/$c
  mount -t cgroup -o $c cgroup $ROOTFS/sys/fs/cgroup/$c
done
```

进 chroot：

```bash
chroot $ROOTFS /bin/bash
```

---

## 四、安装 Docker

### 方式 1：官方静态包（推荐，不依赖 systemd）

```bash
# 在 chroot 内执行
# 先安装基础工具
apt update && apt install -y curl ca-certificates iptables

# 下载最新版 Docker 静态包（aarch64）
curl -fsSL https://download.docker.com/linux/static/stable/aarch64/docker-27.5.1.tgz -o docker.tgz
tar xzf docker.tgz --strip-components=1 -C /usr/local
```

### 方式 2：apt 安装

```bash
apt update
apt install -y docker.io containerd
```

---

## 五、启动 Docker

```bash
# 在 chroot 内，先开 IP 转发（容器出网必需）
sysctl -w net.ipv4.ip_forward=1

# 启动 containerd
containerd >/var/log/containerd.log 2>&1 &

# 启动 dockerd
dockerd >/var/log/dockerd.log 2>&1 &

# 等几秒后验证
docker info
docker version
```

如果 `docker info` 报存储驱动或 cgroup 相关问题，可显式指定：

```bash
dockerd --storage-driver=overlay2 --exec-opt native.cgroupdriver=cgroupfs &
```

---

## 六、运行第一个容器

```bash
docker run --rm hello-world

docker run -it alpine sh
```

---

## 七、常见问题

| 现象 | 原因 / 解决 |
|---|---|
| `dockerd` 启动报 `could not mount cgroup` | cgroup 未挂载，按第三节重新挂载 |
| 容器无网络 / `iptables` 报错 | 检查 `sysctl -w net.ipv4.ip_forward=1`；本内核已内置 `xt_addrtype` 等模块，无需手动 modprobe |
| 报 `operation not permitted` 创建 namespace | 确认以 root 运行，且内核选项已生效（本内核已开启 PID/USER 等命名空间） |
| overlay2 挂载失败 | 本内核已内置 `CONFIG_OVERLAY_FS`；确认 rootfs 所在分区是 ext4 |
| 报 AppArmor 错误 | Android 内核无 AppArmor，属于正常；启动容器加 `--security-opt apparmor=unconfined` 即可忽略 |
| 宿主机内存不足 | 手机 RAM 有限，容器内存限制依赖第三节挂载的 memory cgroup |

---

## 八、内核新增的 Docker 特性（供技术参考）

本次在 `raphael_defconfig` 基础上启用了以下特性（全部编译进内核，`=y`）：

- 命名空间：PID / USER / IPC / NET / UTS
- cgroup：memory、device、pids、net_cls、freezer、cpuacct、cpuset
- OverlayFS（Docker 默认存储驱动 overlay2）
- VETH 虚拟网卡、网桥 + bridge-nf
- nftables、IPv4/IPv6 NAT、MASQUERADE、IPVS、`xt_addrtype` 匹配
- POSIX 消息队列、checkpoint/restore、seccomp

> 已知限制：`CONFIG_CFS_BANDWIDTH` 与高通 `SCHED_WALT` 调度器互斥，无法开启，不影响 Docker 基本功能。

---

## 九、重新构建（复现）

```bash
git clone --depth 1 -b android11 https://github.com/UtsavBalar1231/kernel_xiaomi_raphael.git
git clone --depth 1 https://github.com/kdrag0n/proton-clang.git
export PATH=$PWD/proton-clang/bin:$PATH

cd kernel_xiaomi_raphael
make ARCH=arm64 O=out CC=clang LD=ld.lld CLANG_TRIPLE=aarch64-linux-gnu- \
  CROSS_COMPILE=aarch64-linux-gnu- CROSS_COMPILE_ARM32=arm-linux-gnueabi- raphael_defconfig

# 追加 docker_fragment.config 内容到 out/.config
cat /path/to/docker_fragment.config >> out/.config
make ARCH=arm64 O=out CC=clang LD=ld.lld CLANG_TRIPLE=aarch64-linux-gnu- \
  CROSS_COMPILE=aarch64-linux-gnu- CROSS_COMPILE_ARM32=arm-linux-gnueabi- olddefconfig

make ARCH=arm64 O=out CC=clang AR=llvm-ar NM=llvm-nm OBJCOPY=llvm-objcopy \
  OBJDUMP=llvm-objdump STRIP=llvm-strip LD=ld.lld \
  CLANG_TRIPLE=aarch64-linux-gnu- CROSS_COMPILE=aarch64-linux-gnu- \
  CROSS_COMPILE_ARM32=arm-linux-gnueabi- -j$(nproc) Image
```

产出 `out/arch/arm64/boot/Image` 后，用任意 boot 打包工具（如 `mkbootimg`）按 header v1、kernel_addr=0x00008000 打包即可。
