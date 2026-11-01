# GitHub发布操作

本包未自动创建远端仓库。登录自己的GitHub账号，New repository，名称pynq-helmet-monitor，选择Public，不额外生成README或LICENSE。推荐Git客户端提交仓库根目录的全部文件。确认先运行verify_release.py；不要上传外层github目录或competition目录。

```text
git init -b main
git add .
git commit -m "release verified helmet detection prototype"
```

然后使用GitHub新仓库页面提供的实际remote地址执行git remote add origin与git push。仓库URL确定后填入report/submission_checklist.md；可将本次工程ZIP作为v1.0.0 Release附件。未初始化带私人历史的旧仓库，不包含本地.git或账号配置。所有单文件低于GitHub普通Git单文件100MiB上限；网页上传对单文件另有限制，故推荐Git客户端。
