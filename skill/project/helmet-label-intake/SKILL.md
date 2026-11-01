---
name: helmet-label-intake
description: "本项目专用：接收Make Sense/YOLO标签，检查中文类别映射、缺标签和真实空场。 按既定四类224模型和已验证发布身份工作；其他项目需调整契约。"
---

# 四类标注接收与空场甄别

先读[README.md](README.md)的范围、步骤、历史证据与失效条件，再使用[prompts/workflow.md](prompts/workflow.md)。

以[当前项目契约](../../_shared/project_profile.json)和用户当前要求为准；先确认文件/版本，不自动启动相机、加载PL、付费训练或更改现场入口。

## 本项关键判断

- 先查类别ID映射，中文名称可以映射但不能凭显示名称推断数字顺序。
- 每张可见目标完整标ebike、rider、对应helmet_head或bare_head；只标头部的旧数据另列partial。

交付前逐条检查README失效条件。历史项目验证、本次离线工具验证、尚未执行的实验分开写，不根据模板中的空值补成通过。
