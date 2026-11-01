# DMA 生命周期与接口验证

## 一次事务

1. 获得工程约定的互斥所有权，确认先前 worker/事务退出。
2. 核对位流/元数据、IP 类型及接口配置。
3. 分配或复用有界连续缓冲，检查地址、长度与边界。
4. 写输入，按需 flush/sync_to_device，准备输出接收和参数。
5. 按验证顺序启动接收、计算、发送。
6. 有超时地检查输入、输出、计算和错误状态。
7. invalidate/sync_from_device，检查边界/有效区/数值。
8. 确认停止访问后释放；有约定时恢复原发布并验证恢复结果。

## 协议问题

- TLAST 帧/包边界、TKEEP 有效字节、字节序和打包须与硬件/驱动一致。
- 长度按协议定义，不能把元素个数当字节数；注意 pack4、行尾和 padding。
- FIFO 深度不足、消费者未启动、令牌数量不一致都可能导致部分输出或永久等待。
- DATAFLOW 不证明板上各阶段必然重叠；检查数据依赖、端口竞争和 stall。

## 启动兼容判断

本项目曾遇到 base HWH 与运行时辅助 BRAM 条目差异、合法 DMA 地址落在旧检查范围外、库存 trace DMA 启动后不为 Halt。它们需逐个核对版本和协议，不能推广成忽略所有差异、放宽全部地址或要求所有 DMA Halt。

保护代码阻断时，先列它应证明的事实与当前反例。一次修复只覆盖已确认差异，保留设计身份、地址类型、所有权及退出验证。

## 证据

保留输入/输出、核/模型身份、参数、时钟、完成/错误状态、CPU 对照与 cleanup 状态。日志保存失败与硬件失败单独记录；缺字段不能自动补 PASS。

文件哈希一致只证明文件一致；HWH 含某 IP 不证明其运行，`is_loaded()` 不能替代输出数值核验。

依据：[PYNQ Overlay](https://pynq.readthedocs.io/en/latest/pynq_libraries/overlay.html)、[PYNQ allocate / 缓冲同步](https://pynq.readthedocs.io/en/latest/pynq_libraries/allocate.html)。MMIO 位定义另查当前 AXI DMA/VDMA 版本产品手册。
