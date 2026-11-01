# 技能包：本项目经验与通用PYNQ方法

按比赛3.3.5.2整理：**新增26项项目技能＋此前6项通用PYNQ技能，共32项**。目录名为 `skill/`，每项README明确范围、使用、失效条件、验证效果与来源；可直接读取提示词，也可复用案例模板、校验脚本和踩坑清单。

## 快速复验（不接板卡）

从解压后包含skill/的目录执行。Python3.8+；NPY比较/图片索引另需NumPy。文件核验、报告解析、指标计算与计时摘要使用标准库。

```bash
python skill/verify_skill_bundle.py
python skill/_shared/tools/compare_arrays.py skill/_shared/fixtures/golden_cpu_raw.npy skill/_shared/fixtures/golden_fpga_raw.npy
python skill/_shared/tools/summarize_run.py skill/_shared/fixtures/camera_result_excerpt.json
python skill/_shared/tools/metrics_from_counts.py skill/_shared/fixtures/campus_counts.json
python skill/_shared/tools/check_vivado_reports.py --utilization skill/_shared/fixtures/hardware_utilization.rpt --timing skill/_shared/fixtures/hardware_timing.rpt
```

`python skill/run_offline_checks.py`执行工具的离线行为/故障fixture检查；它不会启动设备。NPY样例是历史CPU/FPGA已保存raw输出，不是人工构造的成功结果。

## 项目技能目录

| 编号 | 项目技能 | 形式 |
|---|---|---|
| 01 | [四类224输入与功能边界冻结](project/helmet-project-contract/README.md) | 提示词工作流＋契约模板 |
| 02 | [发布包身份、完整备份与回退](project/helmet-release-rollback/README.md) | 校验脚本＋踩坑清单 |
| 03 | [四类标注接收与空场甄别](project/helmet-label-intake/README.md) | 校验脚本＋数据接收模板 |
| 04 | [固定224四类训练与轮次归档](project/helmet-train224-rounds/README.md) | 提示词工作流＋实验计划模板 |
| 05 | [ONNX/ncnn导出与算子兼容](project/helmet-export-ncnn-compat/README.md) | 提示词工作流＋接口检查模板 |
| 06 | [FP32到混合精度发布迁移](project/helmet-mixed-precision-migrate/README.md) | 案例模板＋校验工作流 |
| 07 | [ARM切分点与续算参考采集](project/helmet-arm-cutpoint-reference/README.md) | 提示词工作流＋数值校验模板 |
| 08 | [精确激活与再量化ROM生成](project/helmet-activation-rom/README.md) | 硬件案例模板＋域覆盖核验清单 |
| 09 | [178-DSP发布图接入与启动故障定位](project/helmet-overlay-startup/README.md) | 踩坑清单＋身份检查脚本 |
| 10 | [同输入CPU/FPGA逐位一致性验收](project/helmet-cpu-fpga-parity/README.md) | 校验脚本＋黄金数组样例 |
| 11 | [1×1通道分块与可复用乘加阵列](project/helmet-pointwise-mac/README.md) | 硬件提示词工作流＋设计模板 |
| 12 | [3×3紧凑输入、行缓存与整层启动](project/helmet-spatial-streaming/README.md) | 案例模板＋负结果复盘 |
| 13 | [178-DSP双层连续卷积与片上衔接](project/helmet-two-layer-fusion/README.md) | 已验证案例模板＋硬件工作流 |
| 14 | [完整层C++批量调度与接口对齐](project/helmet-native-layer-scheduling/README.md) | 提示词工作流＋交付接口模板 |
| 15 | [ARM续算、NEON与pack4边界成本](project/helmet-arm-suffix-pack4/README.md) | 分析工作流＋优化取舍模板 |
| 16 | [MJPG压缩帧槽与选择性解码](project/helmet-mjpg-latest-frame/README.md) | 已验证工作流＋流水线模板 |
| 17 | [有界后台存证与同帧追溯](project/helmet-async-evidence/README.md) | 案例模板＋所有权检查清单 |
| 18 | [单画面JPEG一次编码与板端画质A/B](project/helmet-single-view-jpeg/README.md) | 已验证案例＋参数实验模板 |
| 19 | [双预览竞争退化的定位与回退](project/helmet-preview-regression/README.md) | 负结果技能＋受控A/B清单 |
| 20 | [411ms计时树与新旧模型同通路A/B](project/helmet-timing-ab-analysis/README.md) | 校验脚本＋性能复盘模板 |
| 21 | [四类检测指标与成功示例追溯](project/helmet-accuracy-evidence/README.md) | 校验脚本＋指标/图像证据模板 |
| 22 | [新模型178-DSP单画面演示与安全收尾](project/helmet-field-demo/README.md) | 操作工作流＋实测记录模板 |
| 23 | [B/C协作任务与候选交付验收](project/helmet-team-handoff/README.md) | 完整提示词模板＋验收矩阵 |
| 24 | [Vivado资源、时序与截图取证](project/helmet-vivado-evidence/README.md) | 校验脚本＋操作清单 |
| 25 | [报告结论、白底流程图与图片归因](project/helmet-report-figures/README.md) | 报告模板＋踩坑清单 |
| 26 | [源码归档、许可证与技能包复现](project/helmet-source-reproducibility/README.md) | 工程骨架＋清单校验脚本 |

## 通用PYNQ技能（单独分区）

- [pynq-board-lab](general/pynq-board-lab/README.md)：排查 PYNQ 板卡的上电、SD 启动、网络/Jupyter 连接、存储容量与残留进程问题；适用于板卡准备和环境诊断，不替代具体 IP 的 DMA 驱动或模型数值验证。
- [pynq-overlay-dma](general/pynq-overlay-dma/README.md)：接入或排查 PYNQ 自定义 Overlay、AXI DMA/VDMA 与 PS/PL 缓冲区通路，核对 bit/HWH、IP 地址、时钟、协议与内存所有权；用于硬件接口及传输问题，不把软件模拟视为上板通过。
- [pynq-model-parity](general/pynq-model-parity/README.md)：更换或接入 PYNQ 推理模型时核对预处理、张量布局、量化和解码契约，逐段比较 CPU/FPGA 同输入结果；适用于 ONNX/ncnn 等模型转换与板端数值验收，不把数值一致当作识别精度。
- [pynq-camera-pipeline](general/pynq-camera-pipeline/README.md)：诊断和优化 PYNQ 摄像头从 UVC/MJPG 采集、解码、推理到 JPEG/Jupyter 显示与后台存储的流水线；用于卡顿、模糊、积压和预览争抢问题，不自动改模型或宣称网络提速。
- [pynq-performance](general/pynq-performance/README.md)：分析 PYNQ 实测日志/JSON，区分采集、完整推理、ARM续算、显示和后台保存计时，设计同通路 A/B 并判断收益；用于低帧率与加速效果争议，不代替精度或 DMA 安全核验。
- [pynq-conv-acceleration](general/pynq-conv-acceleration/README.md)：为 PYNQ/Zynq 的 CNN 热点设计并验证卷积加速，覆盖并行乘加、3×3行缓存、1×1通道/权重复用、层间流水和输出布局，评估 HLS/RTL 资源与整层收益；不把已有位流当作通用加速器。

通用技能在此前已经建立，本次保持单独计数。项目技能绑定四类224契约；通用方法不绑定该模型。无需为使用本提交包把32项都安装进个人全局技能目录：打开相应SKILL.md/README和提示词即可；需要工具时按上面的相对路径运行。

## 共享材料

- [_shared/project_profile.json](_shared/project_profile.json)：类别、输入输出、发布身份与接口；需迁移时先改契约而不是盲改保护检查。
- [_shared/evidence/](_shared/evidence/)：带原来源路径、原文件哈希、提取范围的历史证据片段。保留原状态，包括失败/尚未上板；不是新的验收结果。
- [_shared/fixtures/](_shared/fixtures/)：真实保存raw输出、脱敏计时片段与原实现报告。脚本只读；不会启动相机、操作MMIO、加载PL或训练。
- [catalog.json](catalog.json)：机器可读清单；[validation.json](validation.json)为本次离线验收记录。
- [manifest.json](manifest.json)：技能目录文件哈希；核验只保证列出的文件，不能证明新模型或新板卡已经运行。

## 使用边界与失效条件

1. 项目默认：四类、224输入、两层178-DSP前段＋ARM续算、单带框画面。不恢复越线或信号灯功能。
2. 换模型/板卡/布局/精度/时钟/IP地址时重新填写契约和参考；历史17轮实验属于其原版本，不能冒用为新版本成绩。
3. 独立技能ZIP不含训练图片、权重、位流或ARM依赖；核验生产身份要使用配套完整源码包根目录。整合仓库已附匹配的ncnn ARM依赖，仍需PYNQ系统镜像。
4. 本次确认目录、脚本、历史证据与复验入口；没有新上板、没有新训练，也没有陌生队伍跨题目迁移验收，不声称这些尚未发生的效果。
5. 模板标为NOT_EXECUTED_TEMPLATE；缺材料/数值/完成证据时停止对应结论，不把未知写成成功。

所有用户数据与源文件保持原样。源自失败的技能同样保留负结果，帮助复用者避免把“算对”“某核快”“整层快”“整机快”混为一谈。

离线行为测试默认在skill目录下新建专用临时子目录，结束后自动清理；只读仓库可用--temp-root指定其他已有可写目录。
