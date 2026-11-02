# PL设计源码

本目录保存双层HLS计算源码、匹配常量和浮点尾部。测试台位于sim/pl，测试向量位于data/pl，HLS配置位于build/hls，导出IP位于build/ip，Vivado脚本位于build/vivado。构建前由build/scripts/materialize.py恢复pl组件的原目录关系；不要只取单个cpp直接构建。

源码与原已验证版本保持字节一致，清理版连接工程和历史已验证位流的验证范围见根README。
