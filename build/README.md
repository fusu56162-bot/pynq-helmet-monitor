# 构建与文件恢复

scripts包含只读核验、无覆盖安装、PL重建和原ARM桥接重建入口。payload_map.json将源码、bit/HWH、模型、向量和依赖映射到原运行/构建路径；同一源文件可由多个组件共享，无需重复存放。layout_migration.json记录上一版仓库到当前层级的映射。

reports对应原已验证位流。vivado是清理后的检测专用结构，ip为原匹配导出IP，hls为相对路径HLS配置。实际构建先materialize，避免跨层相对包含出错。
