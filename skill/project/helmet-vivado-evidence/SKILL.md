---
name: helmet-vivado-evidence
description: "本项目专用：从匹配已实现工程提取DSP/BRAM/LUT/FF与时序，并指导报告截图。 按既定四类224模型和已验证发布身份工作；其他项目需调整契约。"
---

# Vivado资源、时序与截图取证

先读[README.md](README.md)的范围、步骤、历史证据与失效条件，再使用[prompts/workflow.md](prompts/workflow.md)。

以[当前项目契约](../../_shared/project_profile.json)和用户当前要求为准；先确认文件/版本，不自动启动相机、加载PL、付费训练或更改现场入口。

## 本项关键判断

- 使用匹配工程Open Implemented Design，不为截图重新Run Implementation。
- 资源看顶层，RAMB36+RAMB18/2换算BRAM Tile；不用子模块/不同位流结果相加。

交付前逐条检查README失效条件。历史项目验证、本次离线工具验证、尚未执行的实验分开写，不根据模板中的空值补成通过。
