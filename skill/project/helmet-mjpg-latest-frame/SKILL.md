---
name: helmet-mjpg-latest-frame
description: "本项目专用：保留相机连续采集，减少USB与ARM不必要的每帧解码/PNG负担。 按既定四类224模型和已验证发布身份工作；其他项目需调整契约。"
---

# MJPG压缩帧槽与选择性解码

先读[README.md](README.md)的范围、步骤、历史证据与失效条件，再使用[prompts/workflow.md](prompts/workflow.md)。

以[当前项目契约](../../_shared/project_profile.json)和用户当前要求为准；先确认文件/版本，不自动启动相机、加载PL、付费训练或更改现场入口。

## 本项关键判断

- 分开记录支持模式、请求模式、实际FOURCC/尺寸和读帧速率，v4l2-ctl缺失不等于不支持MJPG。
- 后台只保留最新压缩payload，识别取到哪个payload就保留其ID并只解码该帧。

交付前逐条检查README失效条件。历史项目验证、本次离线工具验证、尚未执行的实验分开写，不根据模板中的空值补成通过。
