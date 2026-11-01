# 可直接使用的任务提示词：Vivado资源、时序与截图取证

请结合当前四类224输入、178-DSP前段加ARM续算项目，完成以下任务：
从匹配已实现工程提取DSP/BRAM/LUT/FF与时序，并指导报告截图。

我提供的材料位置（按实际填写，不存在就标缺失）：
- 原178图的xpr或routed checkpoint
- 实现后utilization/timing报告
- bit/HWH身份与本次构建阶段

先读取本目录README.md以及../../_shared/project_profile.json。用户当前约束覆盖历史默认配置；不擅自恢复已取消功能，不以历史测量填充本次结果。

执行与判断：
1. 使用匹配工程Open Implemented Design，不为截图重新Run Implementation。
2. 资源看顶层，RAMB36+RAMB18/2换算BRAM Tile；不用子模块/不同位流结果相加。
3. 时序查看Design Timing Summary的Setup/Hold/Pulse Width、失败端点和约束覆盖，保留告警。
4. 清理版只做create_only时仅作结构图，不沿用旧178DSP资源或声称已上板。

输出：
- 资源/时序解析JSON
- 截图步骤和合适图名
- 硬件身份与验证阶段说明

在结尾单独说明：只看正WNS不能证明所有路径被约束。; 语法/结构生成通过不是布局布线通过。; 替代43DSP图和178图不是同时驻留。
区分历史验证、本次离线检查、仍需板端实测。不要把数值一致、识别精度和速度收益混为同一个通过标志。
