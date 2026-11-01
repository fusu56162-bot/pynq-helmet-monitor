---
name: helmet-project-contract
description: "本项目专用：接入模型、改预处理或写报告前，固定本项目四类检测及PS/PL分工。 按既定四类224模型和已验证发布身份工作；其他项目需调整契约。"
---

# 四类224输入与功能边界冻结

先读[README.md](README.md)的范围、步骤、历史证据与失效条件，再使用[prompts/workflow.md](prompts/workflow.md)。

以[当前项目契约](../../_shared/project_profile.json)和用户当前要求为准；先确认文件/版本，不自动启动相机、加载PL、付费训练或更改现场入口。

## 本项关键判断

- 从实际入口追到输入张量，逐项核对RGB/BGR、最近邻缩放、padding、CHW和归一化。
- 确认3087×9输出已经解码，保持ebike/rider/helmet_head/bare_head顺序和分类NMS。

交付前逐条检查README失效条件。历史项目验证、本次离线工具验证、尚未执行的实验分开写，不根据模板中的空值补成通过。
