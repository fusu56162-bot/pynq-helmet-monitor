# 22 新模型178-DSP单画面演示与安全收尾

**形式：** 操作工作流＋实测记录模板。**定位：** 当前四类224输入头盔检测项目的经验包，不是新的板端实验结果。

## 适用范围

用当前已验证Notebook手动演示四类检测，手机拍整机过程并保留必要证据。

## 所需输入

- 匹配的单画面Notebook与受保护文件
- 板卡可达、相机已接、实际关闭其他内核
- 备份与可用容量记录

共享事实先读[项目契约](../../_shared/project_profile.json)。其中类别、阈值、地址、100MHz和178DSP仅适用当前发布版。

## 使用方法

让助手读取本目录SKILL.md，或在支持技能发现的环境调用 `$helmet-field-demo`；将材料位置填入[prompts/workflow.md](prompts/workflow.md)，按下面顺序执行。

1. 区分USB供电与SD启动，检查连接/调焦；不在带电时为拍照改跳帽。
2. 运行初始化核验，再运行单段识别；后续段只改场景参数并运行识别格，不反复清空sessions。
3. 观察CPU和FPGA参考检查完成后才开相机，记录新模型/位流身份和同帧结果。
4. 结束后汇总并按需导出一次；手机录制装置和界面不要求板端完整录像。
5. 确认worker退出、DMA停止与保存结果后正常关机，留停机时间再断电。

结果填入[assets/record-template.json](assets/record-template.json)。它是未执行模板，空值不代表通过。

可复验命令（从含skill/的目录执行）：

```bash
python skill/_shared/tools/verify_release.py --root .
```

```bash
python skill/_shared/tools/summarize_run.py skill/_shared/fixtures/camera_result_excerpt.json
```

`--root .`与manifest.json用于完整源码包；独立技能ZIP不含生产模型/位流，需提供匹配源码根目录。

## 交付物

- 一次演示操作单
- 模型/位流/运行状态摘要
- 照片/视频拍摄与证据下载清单

## 失效条件与停止边界

- programs_stopped=True必须对应实际停止，不能只改变量绕开。
- 启动12组核验是数值检查，不代表24张精度图片。
- 约2.4FPS是在线检测更新率，不宣称流畅30FPS视频或硬实时。

用户只要求分析或手动上板时，完成离线分析/可运行交付后给操作步骤，不自行触发真实设备实验。其他题目先替换模型、布局、时钟、地址和评估定义，再重新验证。

## 已验证的效果

**历史项目证据：** 现行quality_camera入口明确选择profiles/new，真实运行结果记录模型/位流身份；单画面现场已有返回档案。

- [release_identity](../../_shared/evidence/release_identity.json)
- [camera_run](../../_shared/evidence/camera_run.json)
- [quality](../../_shared/evidence/quality.json)

**本次技能包检查：** 见[离线验证记录](../../validation.json)。包括可发现结构、内部引用、模板完整性，以及适用工具的真实归档/故障fixture检查。本次未重开相机、未加载位流、未新训练；尚未进行陌生队伍跨题目迁移验收。

## 从哪些失败或观察中提炼

来自多次现场操作、误删受保护MD、手动停止/关板与拍手机演示需求。

## 迁移到其他工程

保留判断方法，替换本项目契约和黄金参考；如果形状、算子语义、数据来源、并发结构或硬件接口变化，原数值/性能结论不可直接沿用。通用PYNQ方法另列于[general/](../../general/)，不是把项目固定常量推广成通用要求。
