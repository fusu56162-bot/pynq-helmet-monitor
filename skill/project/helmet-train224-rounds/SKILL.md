---
name: helmet-train224-rounds
description: "本项目专用：继续训练当前轻量模型，保持单次整图四类能力与可比验证，不接管云账户。 按既定四类224模型和已验证发布身份工作；其他项目需调整契约。"
---

# 固定224四类训练与轮次归档

先读[README.md](README.md)的范围、步骤、历史证据与失效条件，再使用[prompts/workflow.md](prompts/workflow.md)。

以[当前项目契约](../../_shared/project_profile.json)和用户当前要求为准；先确认文件/版本，不自动启动相机、加载PL、付费训练或更改现场入口。

## 本项关键判断

- 保持224输入和四类顺序，先小规模smoke确认数据/验证/保存链能完成。
- 记录初始化权重、seed、batch、workers、学习率、增强与early-stopping设置；训练轮数不等于独立实验轮次。

交付前逐条检查README失效条件。历史项目验证、本次离线工具验证、尚未执行的实验分开写，不根据模板中的空值补成通过。
