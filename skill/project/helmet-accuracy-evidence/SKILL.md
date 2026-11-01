---
name: helmet-accuracy-evidence
description: "本项目专用：从固定测试记录提取每类P/R、TP/FP/FN及可用于报告的真实预测图。 按既定四类224模型和已验证发布身份工作；其他项目需调整契约。"
---

# 四类检测指标与成功示例追溯

先读[README.md](README.md)的范围、步骤、历史证据与失效条件，再使用[prompts/workflow.md](prompts/workflow.md)。

以[当前项目契约](../../_shared/project_profile.json)和用户当前要求为准；先确认文件/版本，不自动启动相机、加载PL、付费训练或更改现场入口。

## 本项关键判断

- 先区分浮点、混合精度、ARM/FPGA、现场与离线回放；REFERENCE人工框不算预测。
- 按目标而非图像总数计算P/R；空场单独统计误报，不加入有目标召回分母。

交付前逐条检查README失效条件。历史项目验证、本次离线工具验证、尚未执行的实验分开写，不根据模板中的空值补成通过。
