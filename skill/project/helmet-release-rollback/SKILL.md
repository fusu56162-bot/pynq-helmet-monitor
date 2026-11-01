---
name: helmet-release-rollback
description: "本项目专用：整理交付、恢复误删文件、检查完整备份及候选版本隔离。 按既定四类224模型和已验证发布身份工作；其他项目需调整契约。"
---

# 发布包身份、完整备份与回退

先读[README.md](README.md)的范围、步骤、历史证据与失效条件，再使用[prompts/workflow.md](prompts/workflow.md)。

以[当前项目契约](../../_shared/project_profile.json)和用户当前要求为准；先确认文件/版本，不自动启动相机、加载PL、付费训练或更改现场入口。

## 本项关键判断

- 区分完整traffic_project归档、MANIFEST和小结果ZIP，记录各自覆盖范围。
- 先用verify_manifest检查原文件，缺失文档从原包按字节恢复，不重算原清单掩盖差异。

交付前逐条检查README失效条件。历史项目验证、本次离线工具验证、尚未执行的实验分开写，不根据模板中的空值补成通过。
