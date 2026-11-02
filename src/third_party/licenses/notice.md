本作品采用YOLOv5训练框架、Tencent ncnn/pnnx推理转换工具、PYNQ、OpenCV及AMD HLS/Vivado工具。上游版权归各原作者，随包附上游许可与固定版本信息。float_tail/tail_math.h保留其改编算法的原许可说明。HLS导出IP内工具生成文件保留各自原始声明。

上游入口：
- https://github.com/ultralytics/yolov5/tree/v6.2
- https://github.com/Tencent/ncnn/tree/20260526
- https://github.com/Xilinx/PYNQ
- https://github.com/opencv/opencv

项目贡献主要为模型适配、双层PL计算与数值映射、PS/PL桥接、取帧存证调度及实验验证，不将整个上游框架作为自研源码。
