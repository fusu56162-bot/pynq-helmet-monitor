---
name: helmet-arm-cutpoint-reference
description: "本项目专用：在前两层硬件化前确定ncnn边界与可恢复的原ARM输出。 按既定四类224模型和已验证发布身份工作；其他项目需调整契约。"
---

# ARM切分点与续算参考采集

先读[README.md](README.md)的范围、步骤、历史证据与失效条件，再使用[prompts/workflow.md](prompts/workflow.md)。

以[当前项目契约](../../_shared/project_profile.json)和用户当前要求为准；先确认文件/版本，不自动启动相机、加载PL、付费训练或更改现场入口。

## 本项关键判断

- 先证明新桥full与原运行时full一致，再证明boundary→resume与full一致。
- 保存整数累加、激活前后、再量化输入和原raw输出；固定shape/dtype/layout。

交付前逐条检查README失效条件。历史项目验证、本次离线工具验证、尚未执行的实验分开写，不根据模板中的空值补成通过。
