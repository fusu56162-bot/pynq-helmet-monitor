---
name: helmet-native-layer-scheduling
description: "本项目专用：把逐tile Python调度迁到原生层调度，审查B修订候选而不改变现场主入口。 按既定四类224模型和已验证发布身份工作；其他项目需调整契约。"
---

# 完整层C++批量调度与接口对齐

先读[README.md](README.md)的范围、步骤、历史证据与失效条件，再使用[prompts/workflow.md](prompts/workflow.md)。

以[当前项目契约](../../_shared/project_profile.json)和用户当前要求为准；先确认文件/版本，不自动启动相机、加载PL、付费训练或更改现场入口。

## 本项关键判断

- 先固定owned FP32 pack4→owned FP32 pack4 SiLU边界，避免与旧CHW导出时间混比。
- 先静态身份与host整数参考、故障注入、缓冲拥有权，再真实ARM构建与浮点对照。

交付前逐条检查README失效条件。历史项目验证、本次离线工具验证、尚未执行的实验分开写，不根据模板中的空值补成通过。
