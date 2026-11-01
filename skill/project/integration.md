# 整合后使用说明

当前目录已包含完整32项技能。project技能保留_shared依赖，general技能的详细参考用于跨题目迁移。核对本仓库发布身份时执行python skill/_shared/tools/verify_release.py --root .；全仓库文件核验执行python build/scripts/verify_release.py。

若使用verify_manifest检查根目录，manifest路径是manifest.json；技能自身清单是skill/manifest.json。元数据文件改为英文小写，README.md和SKILL.md保留入口标准拼写。历史证据原路径仅用于溯源，不要求其他使用者拥有这些私人路径。
