# 复现与版本说明

1. 运行verify_release.py，核对所有归档身份及六项固定依赖。
2. 用install_board.py在全新目标目录恢复原运行布局，再在PYNQ-Z2官方3.1.1环境安装到固定traffic_project路径。原编译库、对应头文件及源码已经随包提供，运行时只重编轻量桥接层。确认Python3.10、NumPy、OpenCV4.5.4、libgomp和g++可用。
3. 使用新Notebook Kernel，完成文件身份、CPU参考与FPGA参考检查后再开启现场识别。单段30秒；不要同时启用多个硬件会话。复现时记录自己的新FPS，不要求等于短测历史值。
4. PL重建使用build_pl.py。若从源码运行RTL协同仿真，在materialize恢复出的同一hls_float_chain_compact目录依次执行：

```text
vitis-run --mode hls --csim --config hls_config.cfg --work_dir build
v++ -c --mode hls --config hls_config.cfg --work_dir build
vitis-run --mode hls --cosim --config hls_config.cfg --work_dir build
vitis-run --mode hls --package --config hls_config.cfg --work_dir build
```

原配置启用cosim.random_stall，12组C仿真包含全尺寸输入及穷举映射，RTL cosim采用rtl_cases.txt的较小用例；小用例通过不替代完整板级测试。HLS源包含对float_tail的相对引用，因此需恢复整个pl组件，不能只复制单个cpp。

5. 清理后的Vivado连接脚本默认使用已经导出的匹配IP。若重新导出HLS IP，要使用新导出目录更新IP_REPO_PATHS，再重新验证。full阶段到route_design并导出报告；检查DRC、建立/保持时序、DDR板级参数与接口后，在Vivado对新工程生成bitstream，并同时导出同次BD的HWH。新bit/hwh不允许混搭旧文件或沿用旧资源数字。新模型/新位流需更新身份文件并重新采集参考，不能只改哈希来强行通过。

6. 原工程报告和原位流属于同一历史178-DSP设计，后续数值及速度审计另行保存。清理版尚未上板，当前包只验证其结构重建。长期稳定、复杂光照与戴盔独立样本测试仍需补充。

7. 训练脚本保留前轮目录与数据依赖，是研发归档；最终模型推理不依赖云端。若要重训，须恢复所有原始图片标注及前轮依赖，保证划分一致。不能将当前材料称为原始训练数据完整集。


## 本次仓库路径

本仓库按七个一级目录整理，部署及PL重建仍由build/payload_map.json恢复原文件布局。技能已纳入skill，复验命令为python skill/run_offline_checks.py。文件结构图和启动命令以根README.md为准。
