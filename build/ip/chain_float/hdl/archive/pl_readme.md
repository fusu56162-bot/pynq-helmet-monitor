# PL计算源码

`hls_float_chain_compact/src` 是当前新模型前两层计算的原始HLS C++源码；generated/model_data.h和float_tail/generated包含匹配常量。`ip/chain_float`保留其导出IP、Verilog RTL及权重初始化文件。`vision_preprocess`保留兼容接口源码与IP；本次摄像头通路的224预处理实际由ARM软件执行。

`vivado/connected_detection.tcl`在原连接图基础上清理了闲置外设，保留PS参数、两路DMA、预处理及卷积接口、100 MHz和原地址。`build_detection.tcl`仅新建独立项目，默认create_only；不接触板卡，不生成或替换已验证位流。

```powershell
vivado -mode batch -source vivado/build_detection.tcl -tclargs create_only
```

工具版本：Vivado/Vitis HLS 2026.1，xc7z020clg400-1，PYNQ-Z2 board files。HLS配置使用相对路径，应从hls_float_chain_compact目录启动对应HLS工具。已有导出IP可直接用于结构集成。

本次清理版Tcl已在独立目录通过Vivado2026.1的create_only：建立9个顶层模块、validate_bd_design、generate_target、make_wrapper和编译顺序更新完成。仍保留PS/SmartConnect配置提示，未综合、布线或上板。原178-DSP资源/时序及摄像头结果仅对应01_board_verified内的原位流；不得把它们写成清理后新工程的实测指标。新工程须检查DDR板级参数、地址、时钟、DRC、建立/保持时序，再生成成对bit/hwh并补做数值对照。validated_snapshot保留本次通过的BD与顶层包装文件供检查；重新建立工程请使用相对路径Tcl。
