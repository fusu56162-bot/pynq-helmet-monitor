---
name: pynq-model-parity
description: "更换或接入 PYNQ 推理模型时核对预处理、张量布局、量化和解码契约，逐段比较 CPU/FPGA 同输入结果；适用于 ONNX/ncnn 等模型转换与板端数值验收，不把数值一致当作识别精度。"
---

# PYNQ 模型契约与数值核验

## 冻结契约

从已验证入口和模型内容提取：输入尺寸/通道、RGB/BGR、resize 插值、letterbox/padding、归一化、dtype、NCHW/NHWC/pack4、输出节点/形状、坐标尺度、类别顺序、阈值和 NMS。辨明是否已 sigmoid/解码，避免重复处理。

关联模型文件、算子库、编译选项、转换器版本与硬件身份。FP32 ONNX 只是候选格式；同为224输入不保证拓扑、输出、类别、FPGA前段兼容。

## 同输入分段比较

1. 同一原图只生成一次输入张量，保留原图、张量与哈希，两实现使用相同输入。
2. 先比较新/旧软件桥或运行时完整 raw 输出，再比较切分点与恢复续算结果。
3. 定点累加、布局和打包检查精确一致；浮点按算法契约选择逐位或显式容差，不为通过当前失败临时放宽。
4. 上板检查 FPGA 边界、续算 raw 输出，再检查解码和最终框。仅最终框接近可能掩盖中间错误。
5. 正确性后再做纯性能计时。CPU 抽查另计，区分抽查和未查帧，不让错误静默回退 CPU 后继续冒充 FPGA。

样本数量依据边界、形状、量化范围与风险确定；历史12组样本、17轮实验不是通用必跑数量。

`scripts/compare_arrays.py` 仅读两个 `.npy`。默认精确检查 dtype/shape/有限值及元素位模式；容差模式必须显式给 atol/rtol。退出码0=按所选规则一致，1=不一致，2=输入/执行错误；脚本不运行 CPU/FPGA。

```bash
python compare_arrays.py cpu.npy fpga.npy
python compare_arrays.py reference.npy candidate.npy --mode tolerance --atol 0.00001 --rtol 0.000001
```

## 换模型与硬件

- 权重、尺度或激活 ROM 固定时，权重变需匹配的新硬件。数据路径独立于常量且支持加载时，才可能原硬件装新权重。
- 动态权重核也核对尺寸上限、精度、布局、加载协议，不能凭同为 YOLOv5 复用。
- CopyTo 等算子不被当前 ncnn 支持时验证图复制/别名语义，不能批量删节点后只看能加载。
- 新版独立目录验收。旧实验仍是对应版本历史证据，不能直接作新版精度/速度。

## 真实精度与图片

数值相等、准确率、mAP、召回率、整图全对率分别报告。人工参考框不是预测，回放不是现场输出。搜示例先核对 boxes/raw/日志和版本，不补画不存在的成功框。

仅需当前项目背景时读 [references/helmet-project-example.md](references/helmet-project-example.md)；其他项目不照搬类别、维度和哈希。
