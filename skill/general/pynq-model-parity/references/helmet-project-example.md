# 头盔项目历史示例

这是2026-10-30整理的案例，不是PYNQ/YOLO通用契约。以匹配的实际发布包为准。

- 类别：`ebike, rider, helmet_head, bare_head`。
- 输入 `[1,3,224,224]`，raw输出 `[1,3087,9]`。
- BGR 640×480 最近邻缩到224×168，转RGB，上下各补28行值114，CHW float32 /255。
- 55个INT8＋5个FP32卷积；FP32索引6、11、57、58、59。
- 阈值 `[0.35,0.25,0.50,0.20]`，分类NMS 0.45，输出已解码，不二次sigmoid。
- PL固定权重、精确查表的前两层连续卷积，ARM执行后续；不是整网PL。

```text
param 3f4cb05109cc65a1563d557ca44b8a6542282acf7bc73c7f9fd570ac8a271b1d
bin   c07c5773535189d23bc0c9c94fc3377bc2e7713982735c7dced85ff8f49daa9f
bit   77987ca9b7dd4e926df7c720745a242942f9542f729fa081e2ef36074a182f78
hwh   713425cbfe40189cef4fcb0ea999a6bad636b2acf2f4368df8e1a5c2472aa8ed
```

本机来源，不存在时不要猜已核验：

- `D:/Codex/handoffs/final224_speed_20261026_r1/final224_speed_v1`
- `D:/Codex/fpga_work/final224_chain_v1/reference/returned/RESULT.json`
- `D:/Codex/fpga_work/final224_chain_v1/camera_results/20250505_035328_029145c7`

板卡目录2025年、工作站档案2026年，保留原ID，不用文件名推断真实日期。性能用单调时钟。

浮点验证mAP@0.5=0.752不是板端现场75.2%成功率。校园开发集23张中14空场、9有目标，无戴盔正样本；空场不进入有目标召回分母。

新混合精度：电动车TP/FP/FN=9/2/0，骑行者7/2/1，未戴盔2/2/5。数值一致不补足独立场景精度证据。

第四轮回放拼图REFERENCE是人工标注，ROUND3/ROUND4才是预测；不把参考面板作成功示例。当前不含越线、信号灯、乘客角色关联或旁观者自动遮挡。
