---
name: helmet-spatial-streaming
description: "本项目专用：避免ARM重复复制邻域，设计3×3滑窗、输入/计算/输出流水与完整层测试。 按既定四类224模型和已验证发布身份工作；其他项目需调整契约。"
---

# 3×3紧凑输入、行缓存与整层启动

先读[README.md](README.md)的范围、步骤、历史证据与失效条件，再使用[prompts/workflow.md](prompts/workflow.md)。

以[当前项目契约](../../_shared/project_profile.json)和用户当前要求为准；先确认文件/版本，不自动启动相机、加载PL、付费训练或更改现场入口。

## 本项关键判断

- 按可达输入设计预填、三行缓存、左右padding、stride和尾部drain；dilation变化需重算行数。
- 整层一次启动，保留各阶段token数、FIFO深度与回压检查。

交付前逐条检查README失效条件。历史项目验证、本次离线工具验证、尚未执行的实验分开写，不根据模板中的空值补成通过。
