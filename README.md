# MetadataTranslate 1.0.1

MoviePilot V3 插件，宿主接口基线 3.2.5。

补齐 TMDB 缺失语言，支持 DeepL、硅基流动 Hunyuan-MT、OpenRouter、Gemini 和通用接口。多策略共用一个全局服务。可联动 [元数据巡检](https://github.com/JKRaks/mpp-nfochecker)。

## 安装

在 MoviePilot 插件市场添加仓库 `https://github.com/JKRaks/mpp-nfotrans`，安装 MetadataTranslate。仓库包含对应版本完整前端产物。翻译服务需要自行配置 API Key；不上传个人设置或密钥。

## 构建

Node 26.13.0 / npm 11.20.0：

```bash
cd frontend
npm ci
npm run build
cd ..
python3 scripts/package.py
```

构建仅生成本项目的插件。前端类型检查及构建已完成，本版本功能测试尚未执行，已通过本地 MoviePilot 安装及设置接口确认。

[验收交接](TRANSLATION_TESTING.md)描述两个插件的联动场景；另一项目的文件请在对应仓库查阅。未附带真实媒体、运行数据库、私密环境和历史验收截图。

[详细配置说明](plugins.v3/metadatatranslate/README.md) · [云翻译扩展契约](PROVIDERS.md)
