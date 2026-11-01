# 16 MJPG压缩帧槽与选择性解码

**形式：** 已验证工作流＋流水线模板。**定位：** 当前四类224输入头盔检测项目的经验包，不是新的板端实验结果。

## 适用范围

保留相机连续采集，减少USB与ARM不必要的每帧解码/PNG负担。

## 所需输入

- 相机格式枚举和协商回读
- 当前取帧/解码线程代码
- 压缩payload、帧ID和主循环统计

共享事实先读[项目契约](../../_shared/project_profile.json)。其中类别、阈值、地址、100MHz和178DSP仅适用当前发布版。

## 使用方法

让助手读取本目录SKILL.md，或在支持技能发现的环境调用 `$helmet-mjpg-latest-frame`；将材料位置填入[prompts/workflow.md](prompts/workflow.md)，按下面顺序执行。

1. 分开记录支持模式、请求模式、实际FOURCC/尺寸和读帧速率，v4l2-ctl缺失不等于不支持MJPG。
2. 后台只保留最新压缩payload，识别取到哪个payload就保留其ID并只解码该帧。
3. 不把MJPG解码和出板JPEG编码混为同一步；确认原始流无需再压PNG存储。
4. 比较同通路CPU占用、解码耗时、字节、跳帧和帧龄，不把跳过数当FPS提升。

结果填入[assets/record-template.json](assets/record-template.json)。它是未执行模板，空值不代表通过。

可复验命令（从含skill/的目录执行）：

```bash
python skill/_shared/tools/summarize_run.py skill/_shared/fixtures/camera_result_excerpt.json
```

`--root .`与manifest.json用于完整源码包；独立技能ZIP不含生产模型/位流，需提供匹配源码根目录。

## 交付物

- 采集/解码职责图
- 格式回读与实际计时
- 最新帧与跳过/存证语义说明

## 失效条件与停止边界

- 相机声明30FPS不代表板端实际30FPS。
- metadata节点可能不能枚举图像格式。
- 高帧率读压缩流不等于高帧率完整识别。

用户只要求分析或手动上板时，完成离线分析/可运行交付后给操作步骤，不自行触发真实设备实验。其他题目先替换模型、布局、时钟、地址和评估定义，再重新验证。

## 已验证的效果

**历史项目证据：** 真实返回包核验172项payload哈希、原始输入重算与框重解码；相机API返回率和识别率分开记录。

- [mjpg](../../_shared/evidence/mjpg.json)
- [camera_run](../../_shared/evidence/camera_run.json)

**本次技能包检查：** 见[离线验证记录](../../validation.json)。包括可发现结构、内部引用、模板完整性，以及适用工具的真实归档/故障fixture检查。本次未重开相机、未加载位流、未新训练；尚未进行陌生队伍跨题目迁移验收。

## 从哪些失败或观察中提炼

来自相机只读模式查询确认MJPG，以及MJPG取帧/去PNG实测。

## 迁移到其他工程

保留判断方法，替换本项目契约和黄金参考；如果形状、算子语义、数据来源、并发结构或硬件接口变化，原数值/性能结论不可直接沿用。通用PYNQ方法另列于[general/](../../general/)，不是把项目固定常量推广成通用要求。
