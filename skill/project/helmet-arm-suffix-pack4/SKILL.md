---
name: helmet-arm-suffix-pack4
description: "本项目专用：在前段已由FPGA处理后，定位ncnn续算和布局/所有权转换的真实成本。 按既定四类224模型和已验证发布身份工作；其他项目需调整契约。"
---

# ARM续算、NEON与pack4边界成本

先读[README.md](README.md)的范围、步骤、历史证据与失效条件，再使用[prompts/workflow.md](prompts/workflow.md)。

以[当前项目契约](../../_shared/project_profile.json)和用户当前要求为准；先确认文件/版本，不自动启动相机、加载PL、付费训练或更改现场入口。

## 本项关键判断

- 把续算看作forward子区间，不与forward重复相加；该段合并计时不能直接全归某个1×1算子。
- 核查已有NEON和2线程，测布局、Mat所有权复制、缓存与剩余卷积/SiLU，不盲减线程。

交付前逐条检查README失效条件。历史项目验证、本次离线工具验证、尚未执行的实验分开写，不根据模板中的空值补成通过。
