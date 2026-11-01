---
name: helmet-timing-ab-analysis
description: "本项目专用：解释整机2.4FPS、forward180/216ms、ARM续算154/187ms为何同时成立，并选下一步优化。 按既定四类224模型和已验证发布身份工作；其他项目需调整契约。"
---

# 411ms计时树与新旧模型同通路A/B

先读[README.md](README.md)的范围、步骤、历史证据与失效条件，再使用[prompts/workflow.md](prompts/workflow.md)。

以[当前项目契约](../../_shared/project_profile.json)和用户当前要求为准；先确认文件/版本，不自动启动相机、加载PL、付费训练或更改现场入口。

## 本项关键判断

- 建立父子计时和并行支路，ARM续算是forward子项，后台保存不再加主循环。
- 抽查只发生在部分帧，用总耗时/总帧数摊销，不把每次抽查均值当每帧开销。

交付前逐条检查README失效条件。历史项目验证、本次离线工具验证、尚未执行的实验分开写，不根据模板中的空值补成通过。
