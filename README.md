# MetadataTranslate 1.1.3

MoviePilot V3 插件，宿主接口基线 3.2.5。

补齐 TMDB 缺失语言，支持 DeepL、硅基流动 Hunyuan-MT、OpenRouter、Gemini 和通用接口。多策略共用一个全局服务。可联动 [元数据巡检](https://github.com/JKRaks/mpp-nfochecker)。

## 安装

在 MoviePilot 插件市场添加仓库 `https://github.com/JKRaks/mpp-nfotrans`，安装 MetadataTranslate。仓库包含对应版本完整前端产物。翻译服务需要自行配置 API Key；不上传个人设置或密钥。

[详细配置说明](plugins.v3/metadatatranslate/README.md)

安装包可从 [Releases](https://github.com/JKRaks/mpp-nfotrans/releases) 下载；最新构建位于 [Actions](https://github.com/JKRaks/mpp-nfotrans/actions/workflows/package.yml) 成功运行记录的 Artifacts 中，保留 30 天。下载内容包含插件 ZIP 和 SHA256 校验文件。

## 本版界面更新

服务设置集中展示当前服务，高级参数与其他服务按需展开；翻译策略使用摘要卡片，支持模板、复制及默认策略切换。预览直接对比字段变化，调用记录支持单条和批量删除。页面统一提供运行状态、未保存提示和保存操作栏。
