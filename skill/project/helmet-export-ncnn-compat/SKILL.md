---
name: helmet-export-ncnn-compat
description: "本项目专用：固定224导出候选并处理当前ARM ncnn不支持的图算子。 按既定四类224模型和已验证发布身份工作；其他项目需调整契约。"
---

# ONNX/ncnn导出与算子兼容

先读[README.md](README.md)的范围、步骤、历史证据与失效条件，再使用[prompts/workflow.md](prompts/workflow.md)。

以[当前项目契约](../../_shared/project_profile.json)和用户当前要求为准；先确认文件/版本，不自动启动相机、加载PL、付费训练或更改现场入口。

## 本项关键判断

- 分别保留PyTorch、TorchScript/ONNX和ncnn模型身份与固定形状。
- 先逐节点定位不支持算子，如CopyTo，核对复制/别名/生命周期语义，不批量删节点。

交付前逐条检查README失效条件。历史项目验证、本次离线工具验证、尚未执行的实验分开写，不根据模板中的空值补成通过。
