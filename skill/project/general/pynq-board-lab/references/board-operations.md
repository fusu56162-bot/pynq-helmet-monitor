# 板卡操作与故障定位

在板卡终端运行本技能脚本的实际上传路径，例如：

```bash
python inspect_board.py --project /home/xilinx/jupyter_notebooks/my_project
```

可选 `--output board_inventory.json` 新建报告，已存在文件不覆盖。Python 3.8+ 标准库即可；不确认具体 PL 设计或相机实际 FPS。

简单问题优先用现有工具：

```bash
df -h /
df -h /home/xilinx/jupyter_notebooks
du -h --max-depth=1 /home/xilinx/jupyter_notebooks/my_project
ip -brief address
```

`df` 查文件系统可用空间，`du` 查指定目录占用。CMA 余量、普通 MemAvailable、文件系统空间不同。

| 现象 | 优先核查 | 不足以推出的结论 |
|---|---|---|
| 无电源指示、重启 | 电源、线材、跳线、负载 | 浏览器断开不能证明板卡损坏 |
| 有启动迹象、连接不上 | SD 启动、以太网灯、IP/路由 | 网口灯亮不等于 Linux/Jupyter 就绪 |
| IP 可达、端口不可达 | 实际服务与监听端口 | 不要固定猜 80、8888 或历史项目的 9090 |
| 页面可开、内核报错 | 解释器、依赖、目录、原异常 | 不等于需要重刷 SD |
| 文件校验失败 | 发布包与清单，恢复对应原件 | 不先关闭校验 |
| 锁占用、设备忙 | 拥有者、正常停止与退出结果 | 删锁文件不释放旧 inode 上的锁 |
| DMA 异常 | 实际位流、IP 类型、通道与生命周期 | 旧 HWH 列出的 IP 不必都属于当前硬件 |

进程查询采用窄范围，避免把环境变量、账户、令牌打印进报告。重启是已知恢复路径时可用，但不能连续重启替代定位同一前置错误。

## PYNQ-Z2 已核对事实

- Boot 选择 SD/JTAG/QSPI；供电跳线选择 USB/REG，功能不同。
- TUL v1.1 手册：启动 JP1、供电 J9；不套用其他板型的 JP4/JP5。
- PROG UART Micro-USB 与 USB Host 摄像头端口不同。
- Linux 正常停机后再断电；供电灯可能仍亮，不要求所有 LED 先熄灭。

依据：[PYNQ-Z2 Setup Guide](https://pynq.readthedocs.io/en/v2.5.1/getting_started/pynq_z2_setup.html)、[TUL v1.1 手册](https://dpoauwgwqsy2x.cloudfront.net/Download/PYNQ_Z2_User_Manual_v1.1.pdf)。仅适用对应板型/版本。
