# 相机查询、显示与清理

已有工具可只读查询：

```bash
v4l2-ctl -d /dev/video0 --list-formats-ext
v4l2-ctl -d /dev/video0 --get-fmt-video
v4l2-ctl -d /dev/video0 --get-parm
```

声明能力、当前参数、实测FPS不同。缺枚举内容先查节点类型/错误码，不宣布物理相机不支持。

自写查询需核对运行架构的结构体对齐和ioctl号，不把x86_64布局套ARMv7。只枚举用QUERYCAP/ENUM_FMT/ENUM_FRAMESIZES/ENUM_FRAMEINTERVALS，当前状态用G_FMT/G_PARM；不混入S_FMT/S_PARM/S_CTRL/REQBUFS/STREAMON。

依据：[Linux采集接口](https://www.kernel.org/doc/html/latest/userspace-api/media/v4l/dev-capture.html)、[格式查询/设置](https://www.kernel.org/doc/html/latest/userspace-api/media/v4l/vidioc-g-fmt.html)。

OpenCV setter成功仍应回读实际尺寸/FOURCC/FPS和首帧shape，记录backend、版本、节点；驱动可能调整组合。

MJPG入板解码和JPEG出板编码是不同阶段。压缩实验记录分辨率、quality、字节、解码/缩放/编码/提交/推理耗时；顺序单轮的小差异不足以确认稳定提速。

## 模糊和卡顿

- 调焦保持距离、光照可比；改曝光前确认控制支持。
- 比较同一帧raw与解码，不用不同时间姿态当编码差异。
- 深队列可能显示连续但画面很旧，在线监测还需报帧龄。
- display/内核提交结束不是浏览器呈现结束，无端到端时间戳不报相机到屏幕延迟。

## 生命周期

模型/硬件准备与相机实际运行计时分开。启动失败、无帧、推理异常、用户中断分别保留原因。

按依赖停止生产，排空或明确丢弃任务，等待写入/显示退出，再释放资源。join超时不等于线程已停；worker仍持引用时不能释放或启动第二轮共用资源。

保留原始帧ID、输入、输出、框、保存状态。每秒抽样只是保存策略，不改变源头连续采集，也不是完整视频归档。
