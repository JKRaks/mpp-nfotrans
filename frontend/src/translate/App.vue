<script setup lang="ts">
import {computed,onMounted,onUnmounted,ref,shallowRef,watch} from 'vue'
import type {HostProps} from '../types'
import PluginHeader from '../PluginHeader.vue'
import type {Settings,TranslationConfig,Page,PreviewResult} from './types'
import DetailDialog from '../detail/DetailDialog.vue'
import {useDetail} from '../detail/useDetail'
const viewer=useDetail()
const props=defineProps<HostProps & {configView?: boolean}>()
const emit=defineEmits(['close'])
const settings=ref<Settings>(), cfg=ref<TranslationConfig>(), tab=ref('settings'), busy=ref(false), error=ref(''), notice=ref('')
const secrets=ref<Record<string,string|null>>({}), editedProvider=ref('siliconflow_hunyuan')
const keyHelp:Record<string,string>={deepl:'填写 DeepL API 账户的认证密钥，并选择与账户一致的 Free 或 Pro 套餐。',siliconflow_hunyuan:'填写硅基流动控制台创建的 API 密钥，用于调用所填 Hunyuan 模型。',openrouter:'填写 OpenRouter 账户创建的 API Key，用于调用所填模型。',gemini_native:'填写 Google AI Studio 创建的 Gemini API Key；此处使用 Gemini 原生 API。',chat_completions:'填写该兼容服务提供的 API Key，服务地址和模型 ID 也必须属于同一家服务。'}
const showKey=ref(false)
watch(()=>cfg.value?.active_provider,value=>{if(value)editedProvider.value=value})
watch(editedProvider,()=>{showKey.value=false})
const keyStatus=computed(()=>secrets.value[editedProvider.value]===null?'待删除（尚未保存）':secrets.value[editedProvider.value]?'已输入新密钥（尚未保存）':settings.value?.secret_set[editedProvider.value]?'已保存密钥':'尚未配置密钥')
const provider=computed(()=>cfg.value?.provider_configs[editedProvider.value])
const history=shallowRef<Page>(), selected=ref<number[]>([]), status=ref(''), filterProvider=ref('')
const preview=ref({identity:{kind:'movie',tmdb_id:0,season:null as number|null,episode:null as number|null,episode_group:null as string|null,title:'',original_language:null as string|null},nfo:'<movie><title></title><plot></plot><outline></outline></movie>',policy_id:'default',overwrite:false,force:false})
const previewResult=shallowRef<PreviewResult>()
const labels:Record<string,string>={movie:'电影',tv:'整剧',season:'季',episode:'单集',translated:'已翻译',official:'采用来源译文',converted:'繁简转换',kept:'已有目标语言',not_applicable:'不适用',protected:'保护本地修改',language_unknown:'语言待确认',no_source_text:'没有可用原文',failed:'失败',complete:'候选已完成',partial:'部分完成'}
const url=(path:string)=>`plugin/${props.pluginId}/${path}`
let request=0, disposed=false
async function guard(fn:()=>Promise<unknown>){if(busy.value)return;busy.value=true;error.value='';try{await fn()}catch(e:any){const d=e?.response?.data?.detail;error.value=typeof d==='string'?d:d?.message||e?.message||'操作失败'}finally{busy.value=false}}
async function load(){const data=await props.api.get<Settings>(url('settings'));if(disposed)return;settings.value=data;cfg.value=data.config;if(!data.config.policies.some(p=>p.id===preview.value.policy_id))preview.value.policy_id=data.config.default_policy}
async function save(){if(!cfg.value)return;await props.api.post(url('settings'),{config:cfg.value,secrets:secrets.value});secrets.value={};await load();notice.value='配置已保存'}
function addPolicy(){cfg.value?.policies.push({id:crypto.randomUUID(),name:'新翻译策略',target_language:'zh-CN',fields:['plot','outline'],kinds:['movie','tv','season','episode'],mode:'translate',fallback_languages:['zh-TW','en-US','original'],chinese_conversion:true,prefer_official:true})}
function split(value:string){return value.split(/[\n,，]/).map(x=>x.trim()).filter(Boolean)}
async function loadHistory(page=1){const id=++request;const value=await props.api.get<Page>(url('history'),{params:{page,page_size:30,status:status.value,provider:filterProvider.value}});if(!disposed&&id===request){history.value=value;selected.value=[]}}
async function openTab(value:string){tab.value=value;if(value==='history')await loadHistory()}
async function runPreview(){await save();await viewer.show('翻译输出详情',async()=>{const result=await props.api.post<PreviewResult>(url('preview'),preview.value);previewResult.value=result;return result})}
async function test(){await save();const result=await props.api.post<Record<string,unknown>>(url('test'));const sample=result.sample as {status?:string;text?:string;message?:string}|undefined;notice.value=sample?.status==='translated'?'连接成功，示例译文：'+sample.text:'连接未成功：'+(sample?.message||'请检查服务配置')}
async function clearCache(kind:string){const result=await props.api.post<{cache:Record<string,number>}>(url('cache/clear'),{kind});if(settings.value)settings.value.cache=result.cache;notice.value='缓存已清理，媒体文件和调用记录保留'}
async function remove(){if(!selected.value.length)return;await props.api.post(url('delete'),{ids:selected.value});viewer.close();await loadHistory(history.value?.page||1)}
async function showDetail(id:number){await viewer.show('翻译调用详情',()=>props.api.get(url('detail'),{params:{id}}))}
onMounted(()=>guard(load));onUnmounted(()=>{disposed=true;request++})
</script>

<template>
<main class="translate-app">
  <PluginHeader :title="configView ? '元数据翻译 - 插件配置' : '元数据翻译'" @close="emit('close')" />
  <div class="plugin-content">
  <p class="hint">补齐缺少的目标语言，所有规则共用当前全局翻译服务。</p>
  <p v-if="error" role="alert" class="error">{{error}}</p><pre v-if="notice" class="notice" role="status">{{notice}} <button @click="notice=''">关闭</button></pre>
  <nav><button v-for="t in [{id:'settings',name:'服务设置'},{id:'policies',name:'翻译策略'},{id:'preview',name:'翻译预览'},{id:'history',name:'调用记录'}]" :key="t.id" :disabled="busy" :class="{active:tab===t.id}" @click="guard(()=>openTab(t.id))">{{t.name}}</button></nav>
  <p v-if="!cfg">正在加载…</p>
  <template v-if="cfg&&settings">
    <div class="toolbar"><label><input type="checkbox" v-model="cfg.enabled" :disabled="busy">启用翻译服务</label><button :disabled="busy" @click="guard(save)">保存设置</button><span v-if="busy">正在处理…</span></div>
    <p v-if="settings.busy" class="hint">存在活动翻译批次，结束后才能保存配置。关闭页面不会停止后台巡检。</p>
    <section v-if="tab==='settings'">
      <fieldset :disabled="busy"><legend>1 · 选择使用的服务</legend><label>当前启用的翻译服务<select v-model="cfg.active_provider"><option value="">尚未选择</option><option v-for="(name,id) in settings.providers" :value="id" :key="id">{{name}}</option></select></label><p class="hint">所有策略共用一家服务。失败后保留待重试，不自动切换其他服务或模型；切换不会重写已有译文。</p>
        <label><input type="checkbox" v-model="cfg.global_hook">增强官方 NFO 刮削</label><label>官方刮削默认策略<select v-model="cfg.default_policy"><option v-for="p in cfg.policies" :key="p.id" :value="p.id">{{p.name}}</option></select></label>
        <p v-if="settings.hook_conflicts.length" class="error">检测到其他 NFO 扩展：{{settings.hook_conflicts.join('、')}}。全局接管暂停，NfoCheck 显式翻译仍可使用。</p>
        <p class="hint">官方路径只增强候选内容，覆盖与备份由宿主控制；已有媒体的保护、备份和恢复请使用 NfoCheck。</p>
      </fieldset>
      <fieldset :disabled="busy"><legend>2 · 填写服务与密钥</legend><label>正在编辑的服务<select v-model="editedProvider"><option v-for="(name,id) in settings.providers" :value="id" :key="id">{{name}}</option></select></label>
        <template v-if="provider">
          <p class="service-summary">正在编辑：<strong>{{settings.providers[editedProvider]}}</strong> · 当前使用：<strong>{{settings.providers[cfg.active_provider]||'尚未选择'}}</strong></p>
          <p v-if="editedProvider!==cfg.active_provider" class="hint">此处只修改该服务的配置。要使用它，请先在上方“当前启用的翻译服务”中选择它。</p>
          <div class="key-card">
            <label :for="'provider-key-'+editedProvider">{{settings.providers[editedProvider]}} API Key（接口密钥）</label>
            <p class="key-status" role="status">{{keyStatus}}</p>
            <div class="key-input"><input :id="'provider-key-'+editedProvider" :type="showKey?'text':'password'" autocomplete="new-password" spellcheck="false" :value="secrets[editedProvider]||''" @input="secrets[editedProvider]=($event.target as HTMLInputElement).value.trim()" :placeholder="settings.secret_set[editedProvider]?'已有密钥；仅更换时填写新密钥':'粘贴此服务的 API Key'"><button type="button" :aria-pressed="showKey" @click="showKey=!showKey">{{showKey?'隐藏输入':'显示输入'}}</button></div>
            <p>{{keyHelp[editedProvider]}}</p>
            <p class="hint">仅粘贴密钥本身，不要添加 Bearer、Authorization 或引号。已保存的密钥不会回显；留空并保存会保留旧密钥。填写新密钥后，点击“保存设置”才会替换。</p>
            <button v-if="secrets[editedProvider]!==null" type="button" :disabled="!settings.secret_set[editedProvider]&&!secrets[editedProvider]" @click="secrets[editedProvider]=null">标记删除该服务密钥</button>
            <template v-else><p class="error">保存设置后将删除 {{settings.providers[editedProvider]}} 的密钥，该服务将无法调用。</p><button type="button" @click="delete secrets[editedProvider]">撤销删除</button></template>
          </div>
          <label v-if="editedProvider==='deepl'">DeepL 套餐<select v-model="provider.deepl_plan"><option value="free">API Free</option><option value="pro">API Pro</option></select></label>
          <template v-else><label>服务地址<input v-model="provider.endpoint" :placeholder="editedProvider==='gemini_native'?'https://generativelanguage.googleapis.com':'完整 chat/completions 地址'"></label><label>模型 ID<input v-model="provider.model" placeholder="填写准确模型标识"></label></template>
          <label v-if="editedProvider==='gemini_native'">API 版本<select v-model="provider.api_version"><option>v1beta</option><option>v1</option></select></label>
          <label v-if="!['deepl','siliconflow_hunyuan'].includes(editedProvider)">响应模式<select v-model="provider.response_mode"><option value="prompt_json">提示词约束 JSON</option><option value="json_object">JSON Object</option><option value="json_schema">JSON Schema</option></select></label>
          <p v-if="editedProvider==='siliconflow_hunyuan'" class="hint">默认 tencent/Hunyuan-MT-7B；单段纯文本翻译，不发送 JSON 输出要求。</p>
          <p v-if="editedProvider==='openrouter'" class="hint">使用指定模型，关闭备用模型与上游失败回退；初始上游由 OpenRouter 选择。</p>
          <div class="grid"><label>每次文本字符上限<input type="number" min="100" max="100000" v-model.number="provider.max_chars"></label><label v-if="editedProvider!=='deepl'">最大输出 token<input type="number" min="128" max="32768" v-model.number="provider.max_output_tokens"></label></div>
        </template>
      </fieldset>
      <fieldset :disabled="busy"><legend>3 · 请求与缓存（可保留默认值）</legend><div class="grid"><label>单次时限（秒）<input type="number" min="5" max="120" v-model.number="cfg.timeout"></label><label>并发数<input type="number" min="1" max="8" v-model.number="cfg.concurrency"></label><label>来源缓存（小时）<input type="number" min="1" v-model.number="cfg.source_hours"></label><label>无原文复查间隔（天）<input type="number" min="1" v-model.number="cfg.missing_days"></label><label>译文缓存（天）<input type="number" min="1" v-model.number="cfg.cache_days"></label><label>调用记录保留（天）<input type="number" min="1" v-model.number="cfg.history_days"></label></div>
        <p>缓存：来源 {{settings.cache.source||0}} 条，译文 {{settings.cache.translation||0}} 条。</p><div class="toolbar"><button @click="guard(()=>clearCache('source'))">清理来源缓存</button><button @click="guard(()=>clearCache('translation'))">清理译文缓存</button></div>
      </fieldset>
      <button :disabled="busy||!cfg.enabled||!cfg.active_provider" @click="guard(test)">保存并测试 {{settings.providers[cfg.active_provider]||'当前服务'}}</button><p class="hint">测试对象是上方“当前启用的翻译服务”，不是仅在编辑的服务。连接测试会发送一句固定示例，可能产生服务费用；不会读取或写入媒体文件。</p>
    </section>
    <section v-if="tab==='policies'">
      <fieldset v-for="(p,index) in cfg.policies" :key="p.id" :disabled="busy"><legend>{{p.name}}</legend><div class="grid"><label>名称<input v-model="p.name"></label><label>目标语言<input v-model="p.target_language" placeholder="例如 zh-CN"><small class="hint">简体中文 zh-CN · 繁体中文 zh-TW · 英语 en-US</small></label><label>模式<select v-model="p.mode"><option value="translate">缺失时自动翻译</option><option value="source_only">仅来源补齐及繁简转换</option></select></label><label>备用语言（按顺序，每行一个）<textarea :value="p.fallback_languages.join('\n')" @input="p.fallback_languages=split(($event.target as HTMLTextAreaElement).value)" /></label></div>
        <p class="hint">original 表示作品原语言。源数据没有任何原文时不会生成剧情。</p>
        <div class="toolbar"><label v-for="(name,id) in settings.fields" :key="id"><input type="checkbox" :value="id" v-model="p.fields">{{name}}</label></div><div class="toolbar"><label v-for="kind in ['movie','tv','season','episode']" :key="kind"><input type="checkbox" :value="kind" v-model="p.kinds">{{labels[kind]}}</label></div>
        <label><input type="checkbox" v-model="p.chinese_conversion">允许中文繁简转换</label><label><input type="checkbox" v-model="p.prefer_official">来源补齐正式译文后，替换未被手工修改的机器译文</label><p class="hint">标题默认不选；原始标题、人名、媒体 ID 和季集号不进入翻译。</p>
        <button :disabled="p.id===cfg.default_policy" @click="cfg.policies.splice(index,1)">删除策略</button>
      </fieldset><button :disabled="busy" @click="addPolicy">添加策略</button>
    </section>
    <section v-if="tab==='preview'">
      <p class="hint">使用明确 TMDB 身份和粘贴的 NFO 预览。会调用所选服务并保存缓存，不写媒体或刷新 Emby。真实应用在 NfoCheck 中执行。</p>
      <fieldset :disabled="busy"><div class="grid"><label>策略<select v-model="preview.policy_id"><option v-for="p in cfg.policies" :key="p.id" :value="p.id">{{p.name}}</option></select></label><label>媒体类型<select v-model="preview.identity.kind"><option v-for="kind in ['movie','tv','season','episode']" :key="kind" :value="kind">{{labels[kind]}}</option></select></label><label>TMDB ID（季集填整剧 ID）<input type="number" min="1" v-model.number="preview.identity.tmdb_id"></label><label>作品名（可选）<input v-model="preview.identity.title"></label><label v-if="['season','episode'].includes(preview.identity.kind)">季号<input type="number" min="0" v-model.number="preview.identity.season"></label><label v-if="preview.identity.kind==='episode'">集号<input type="number" min="1" v-model.number="preview.identity.episode"></label><label v-if="['season','episode'].includes(preview.identity.kind)">分集组 ID（可选）<input :value="preview.identity.episode_group||''" @input="preview.identity.episode_group=($event.target as HTMLInputElement).value||null"></label></div>
        <label>NFO 内容<textarea class="xml" v-model="preview.nfo" /></label><label><input type="checkbox" v-model="preview.overwrite">本次允许替换无法确认来源的本地文字</label><label><input type="checkbox" v-model="preview.force">本次绕过译文缓存</label><button :disabled="!cfg.enabled" @click="guard(runPreview)">保存设置并生成预览</button>
      </fieldset>
      <div v-if="previewResult"><p>候选变化 {{previewResult.changed_fields.length}} 字段；待处理 {{previewResult.pending_fields.length}} 字段。</p><button @click="viewer.show('翻译输出详情',previewResult)">查看输出详情</button><button @click="viewer.show('候选 NFO 详情',{nfo:previewResult.nfo})">查看候选 NFO</button></div>
    </section>
    <section v-if="tab==='history'">
      <div class="toolbar"><select v-model="filterProvider" aria-label="服务筛选"><option value="">全部服务</option><option v-for="(name,id) in settings.providers" :key="id" :value="id">{{name}}</option></select><select v-model="status" aria-label="状态筛选"><option value="">全部状态</option><option value="complete">已完成</option><option value="partial">部分完成</option><option value="failed">失败</option><option value="translated">连接测试成功</option></select><button :disabled="busy" @click="guard(()=>loadHistory())">查询</button><button :disabled="busy||!history?.items.length" @click="selected=history?.items.map(x=>x.id)||[]">选择本页</button><button :disabled="busy||!selected.length" @click="guard(remove)">删除选中记录</button></div>
      <p class="hint">记录描述翻译候选或连接测试，不代表媒体文件已写入。删除记录不删除缓存、备份或巡检待办。</p>
      <article v-for="row in history?.items" :key="row.id"><label><input type="checkbox" :value="row.id" v-model="selected">{{new Date(row.created*1000).toLocaleString()}} · {{settings.providers[row.provider]||'来源补齐'}} · {{labels[row.status]||row.status}}</label><p>{{row.summary}}</p><button :disabled="busy" @click="showDetail(row.id)">详情</button></article>
      <div v-if="history" class="toolbar"><button :disabled="busy||history.page<=1" @click="guard(()=>loadHistory((history?.page||1)-1))">上一页</button><span>第 {{history.page}} 页 · {{history.total}} 条</span><button :disabled="busy||history.page*history.page_size>=history.total" @click="guard(()=>loadHistory((history?.page||1)+1))">下一页</button></div>
    </section>
  </template>
</div>
<DetailDialog :opened="viewer.opened.value" :title="viewer.title.value" :loading="viewer.loading.value" :error="viewer.error.value" :data="viewer.data.value" @close="viewer.close" />
</main>
</template>

<style scoped>
.plugin-content{padding:20px;min-width:0}

.translate-app{width:100%;margin:auto;padding:0;font-family:inherit;font-size:14px;line-height:1.6;color:rgb(var(--v-theme-on-surface,40,44,52))}.translate-app *{box-sizing:border-box}h2{margin-bottom:0}nav,.toolbar{display:flex;flex-wrap:wrap;gap:12px;align-items:center;margin:18px 0}fieldset,article{border:1px solid #8885;border-radius:10px;padding:18px;margin:18px 0;min-width:0}legend,h3{font-weight:600}label{display:flex;gap:8px;align-items:center;margin:10px 0}label:has(input:not([type=checkbox])),label:has(select),label:has(textarea){flex-direction:column;align-items:stretch}.grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}input,textarea,select,button{font:inherit;color:inherit;background:rgb(var(--v-theme-surface,255,255,255));border:1px solid #8886;border-radius:6px;padding:8px;min-width:0}button{cursor:pointer}button:disabled,fieldset:disabled{opacity:.5}input[type=checkbox]{accent-color:#5269cd}.active{background:#5269cd;color:white}textarea{min-height:110px;resize:vertical}.xml{min-height:220px;font-family:monospace}pre{white-space:pre-wrap;overflow-wrap:anywhere;padding:12px;background:#8881;border-radius:8px}.error{color:#c74941}.hint{opacity:.72}.notice{background:#5269cd15}article p{overflow-wrap:anywhere}@media(max-width:700px){.grid{grid-template-columns:1fr}.plugin-content{padding:12px}fieldset,article{padding:12px}}
.key-card{padding:16px;background:#5269cd0a;border:1px solid #5269cd44;border-radius:8px;margin:16px 0}.key-card>label{font-weight:600;align-items:flex-start}.key-status{font-weight:600}.key-input{display:flex;gap:8px;align-items:center}.key-input input{flex:1;width:100%;min-width:0}.key-input button{flex-shrink:0}.service-summary{padding:10px 12px;background:#8881;border-radius:6px}.grid>label{min-width:0}.grid input,.grid select,.grid textarea{width:100%}nav{gap:8px}button:focus-visible,input:focus-visible,select:focus-visible,textarea:focus-visible{outline:2px solid #5269cd;outline-offset:2px}@media(max-width:700px){.key-card{padding:12px}.key-input{flex-wrap:wrap}.key-input input{flex-basis:100%}nav button{flex:1 1 40%}}
</style>
