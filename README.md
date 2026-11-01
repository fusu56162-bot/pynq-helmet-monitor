# 基于 PYNQ Z2 的校园骑行头盔在线监测系统

基于PYNQ-Z2 / Zynq-7020（xc7z020clg400-1）的四类视频流在线检测原型。USB摄像头持续输出MJPG，模型识别电动自行车、骑行者、戴盔头部和未戴盔头部。PL完成前两层连续卷积及相关激活量化，ARM双线程ncnn完成后续网络，浏览器显示同帧检测框并抽样保存证据。

本仓库按AMD自主选题指南3.3.5.4分层，包含26项项目技能与6项通用PYNQ技能，共32项。当前应用不含越线判定和交通灯控制。

## 目录

```text
pynq_helmet_monitor/
├── README.md
├── LICENSE
├── NOTICE.md
├── src/       # PS、HLS、训练转换与第三方对应源码
├── sim/       # 仿真、板级审计与本次整合检查
├── build/     # 构建脚本、IP、Vivado连接脚本及实现报告
├── board/     # 成对bit/HWH、Notebook、ARM依赖与安装指南
├── data/      # 模型、测试输入、边界与黄金输出
├── skill/     # project 26项、general 6项、共享工具和参考
└── report/    # 最新设计报告文本、流程图、实验台账与协作原文
```

目录及普通文件名为英文小写；README.md、SKILL.md、LICENSE、NOTICE.md保留通用入口拼写。中文仅用于文件正文。原板端文件名通过映射恢复，避免改写受保护运行文件。

## 已验证结果

| 指标 | 条件与结果 |
|---|---|
| 模型契约 | 输入float32 [1,3,224,224]，输出[1,3087,9]，四类固定顺序 |
| 硬件 | 100MHz，DSP178/220，BRAM Tile30.5/140，LUT23463，寄存器24221 |
| 时序 | WNS0.949ns，WHS0.015ns |
| 同输入离线forward | CPU204.27ms，FPGA+ARM180.31ms，延迟下降11.73%，约1.13倍 |
| 摄像头检测更新 | 73帧/30.011秒，2.4324FPS；包含显示提交、CPU抽查及抽样存证 |
| 数值验证 | 启动12组CPU与12组FPGA参考核对，现场按周期抽查 |

forward计时包含打包、缓存、DMA与ARM续算，不包含相机和显示。浮点验证集mAP@0.5为0.752（60张），不等于板端现场识别成功率。小目标未戴盔仍有漏检，长期稳定性未完成验收。

## 电脑上检查

Python3.10+，离线工具中的数组检查需要NumPy。无需摄像头或板卡：

```text
python build/scripts/verify_release.py
python skill/verify_skill_bundle.py
python skill/run_offline_checks.py
python skill/_shared/tools/verify_release.py --root .
```

核验覆盖全部仓库文件、四项发布身份、六项固定ARM依赖、32项技能结构和离线工具行为。验证范围及结果见sim/github_validation.json。技能目录见[skill/README.md](skill/README.md)，报告见[report/design_report.md](report/design_report.md)。

## 安装到板卡

准备PYNQ3.1.1的32位ARMv7环境，确认Python3.10、NumPy、OpenCV4.5.4、g++和libgomp。仓库已附原固定ncnn源码、头文件及静态/共享库，无需从私人备份另找这六项依赖。系统从SD卡启动，供电与跳线沿用已验证配置。原现场通过网线访问 http://192.168.2.99:9090 。

```text
python build/scripts/install_board.py --destination restore_preview --check-only
python build/scripts/install_board.py --destination /home/xilinx/jupyter_notebooks/traffic_project
```

安装脚本会先检查所有文件，目标存在不同文件时停止，不覆盖原工程；不会加载PL或打开相机。它将英文仓库路径按build/payload_map.json恢复成原运行布局，保留原清单、文档和程序字节。

安装后在新Kernel打开camera_quality_v1中的“打开我_现场演示_已验证178DSP.ipynb”，依次运行初始化格和30秒识别格；结束后按需导出。默认new模型、Q80、宽640、一个带框画面。先停止其他相机/FPGA会话并保留已有备份。程序输出抽样证据，连续演示视频由手机另行拍摄。

## 从源码构建

AMD Vivado / Vitis HLS 2026.1及PYNQ-Z2 board files。每条命令使用新输出目录：

```text
python build/scripts/build_pl.py --output work_pl_create --phase create_only
python build/scripts/build_pl.py --output work_pl_csim --phase csim
python build/scripts/build_pl.py --output work_pl_synth --phase synthesis
python build/scripts/build_pl.py --output work_pl_full --phase full
```

build_pl.py先恢复完整PL布局再启动工具；full到route_design并导出资源、时序和DRC供核对。重新生成硬件后需同时导出匹配bit/HWH并重新上板验收，不能直接替换原文件。具体C仿真、RTL cosim和ARM重建步骤见[复现说明](report/reproduction.md)。

## 硬件版本与功能范围

现场已验证的178-DSP bit/HWH保留原始字节和历史闲置外设元数据。检测专用源码及BD已去除对应外设控制逻辑，已通过2026.1结构重建，但尚未重新布局布线或上板。build/reports内的178-DSP资源与时序对应历史已验证位流。工具生成文件和历史报告中的旧实例名称不表示当前应用启用了旧功能。不能手工删改HWH后仍声称与原bit匹配。

## 训练与许可

src/training保留训练、导出、量化和兼容修复工具；report/evidence/training保留五批配置、CSV和评价摘要。原始训练照片与完整标注数据集未随公开包提供，重训需另行恢复；冻结部署模型和数值参考已随包提供。

项目原创代码按GPL-3.0发布，采用YOLOv5 v6.2固定版，ncnn与改编数学代码保留BSD/zlib声明，AMD生成文件保留原版权声明。详见LICENSE、NOTICE.md和src/third_party/licenses。

这是可上传GitHub的本地仓库包，尚未创建或上传远端仓库。解压后使用pynq_helmet_monitor目录作为仓库根目录，发布步骤见[GitHub操作说明](report/github_publish.md)。
