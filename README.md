# MetadataTranslate 1.0.4

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

[详细配置说明](plugins.v3/metadatatranslate/README.md) · [云翻译扩展契约](PROVIDERS.md)

## 本版界面更新

详情使用弹窗，提供中文字段分组与原始内容切换；两个插件采用统一全宽标题栏及关闭按钮。

## 代码格式

Python 使用 Black（行宽 100），前端及 JSON 使用 Prettier。

```bash
python -m black plugins.v3/metadatatranslate scripts
npx prettier --write "frontend/src/**/*.{vue,ts,json}" frontend/vite.config.ts frontend/index.html frontend/tsconfig.json package.v3.json examples/*.json
```
