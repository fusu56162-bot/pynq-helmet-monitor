---
name: helmet-cpu-fpga-parity
description: "本项目专用：区分同输入实现正确与识别精度，验证当前178前段加ARM续算。 按既定四类224模型和已验证发布身份工作；其他项目需调整契约。"
---

# 同输入CPU/FPGA逐位一致性验收

先读[README.md](README.md)的范围、步骤、历史证据与失效条件，再使用[prompts/workflow.md](prompts/workflow.md)。

以[当前项目契约](../../_shared/project_profile.json)和用户当前要求为准；先确认文件/版本，不自动启动相机、加载PL、付费训练或更改现场入口。

## 本项关键判断

- 先核shape/dtype，再查有限值和位模式，不只对最终框。
- 定点、打包及当前精确参考按逐位；任何近似实现另立事先约定容差。

交付前逐条检查README失效条件。历史项目验证、本次离线工具验证、尚未执行的实验分开写，不根据模板中的空值补成通过。
