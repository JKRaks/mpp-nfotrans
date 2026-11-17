<script setup lang="ts">
import { computed, inject, ref, shallowRef, toRefs, watch } from 'vue'
import { TRANSLATION_KEY, fieldNames, labels } from '../useTranslation'
import type { PreviewInput, PreviewResult } from '../types'
const state = inject(TRANSLATION_KEY)!
const { cfg, settings, dirty, busy, locked, configurationIssue, serviceIssue } = toRefs(state)
function emptyNfo(kind: string) {
  const root = (
    { movie: 'movie', tv: 'tvshow', season: 'season', episode: 'episodedetails' } as Record<
      string,
      string
    >
  )[kind]
  return `<${root}>\n  <title></title>\n  <plot></plot>\n  <outline></outline>\n</${root}>`
}
const preview = ref<PreviewInput>({
  identity: {
    kind: 'movie',
    tmdb_id: null,
    season: null,
    episode: null,
    episode_group: null,
    title: '',
    original_language: null,
  },
  nfo: emptyNfo('movie'),
  policy_id: cfg.value?.default_policy || 'default',
  overwrite: false,
  force: false,
})
const result = shallowRef<PreviewResult>(),
  inputNfo = ref(''),
  resultFingerprint = ref('')
const fingerprint = computed(() =>
  JSON.stringify([preview.value, cfg.value, settings.value?.revision, state.secrets]),
)
const stale = computed(() => !!result.value && resultFingerprint.value !== fingerprint.value)
const policy = computed(() => cfg.value?.policies.find((p) => p.id === preview.value.policy_id))
watch(
  () => cfg.value?.policies.map((p) => p.id),
  (ids) => {
    if (ids && !ids.includes(preview.value.policy_id))
      preview.value.policy_id = cfg.value?.default_policy || ''
  },
)
watch(
  () => preview.value.identity.kind,
  (kind, before) => {
    if (preview.value.nfo === emptyNfo(before)) preview.value.nfo = emptyNfo(kind)
    if (kind !== 'episode') preview.value.identity.episode = null
    if (!['season', 'episode'].includes(kind)) {
      preview.value.identity.season = null
      preview.value.identity.episode_group = null
    }
  },
)
const previewIssue = computed(() => {
  if (!cfg.value?.enabled) return '请先启用翻译服务'
  if (!policy.value) return '请选择翻译策略'
  if (!policy.value.kinds.includes(preview.value.identity.kind))
    return '当前策略未包含该媒体类型，请调整策略或媒体类型'
  if (configurationIssue.value) return configurationIssue.value
  if (policy.value.mode === 'translate' && serviceIssue.value) return serviceIssue.value
  const identity = preview.value.identity
  if (!Number.isInteger(identity.tmdb_id) || Number(identity.tmdb_id) < 1)
    return '请填写有效的 TMDB ID'
  if (
    ['season', 'episode'].includes(identity.kind) &&
    (!Number.isInteger(identity.season) || Number(identity.season) < 0)
  )
    return '请填写季号，特别篇可填 0'
  if (
    identity.kind === 'episode' &&
    (!Number.isInteger(identity.episode) || Number(identity.episode) < 1)
  )
    return '请填写有效的集号'
  if (!preview.value.nfo.trim()) return '请填写 NFO 内容'
  return ''
})
function nfoFields(nfo: string) {
  const doc = new DOMParser().parseFromString(nfo, 'application/xml')
  return Object.fromEntries(
    Object.keys(fieldNames).map((field) => [
      field,
      Array.from(doc.documentElement.children)
        .filter((node) => node.tagName === field)
        .map((node) => node.textContent || '')
        .join('\n'),
    ]),
  )
}
const comparisons = computed(() => {
  if (!result.value) return []
  const before = nfoFields(inputNfo.value),
    after = nfoFields(result.value.nfo)
  return Object.entries(result.value.fields).map(([field, value]) => ({
    field,
    ...value,
    before: value.before ?? before[field],
    after: after[field],
    changed: result.value!.changed_fields.includes(field),
  }))
})
async function generate() {
  if (previewIssue.value) throw new Error(previewIssue.value)
  await state.save()
  const payload = JSON.parse(JSON.stringify(preview.value)) as PreviewInput
  if (!payload.identity.episode_group?.trim()) payload.identity.episode_group = null
  result.value = undefined
  const stamp = fingerprint.value
  const output = await state.api.post<PreviewResult>(state.url('preview'), payload)
  inputNfo.value = payload.nfo
  resultFingerprint.value = stamp
  result.value = output
}
</script>
<template>
  <section v-if="cfg" aria-label="翻译预览">
    <fieldset class="preview-form" :disabled="busy">
      <div class="section-heading">
        <h3>选择策略与媒体</h3>
        <span class="hint">使用明确的 TMDB 身份生成候选</span>
      </div>
      <div class="grid">
        <label
          >翻译策略<select v-model="preview.policy_id">
            <option v-for="p in cfg.policies" :key="p.id" :value="p.id">{{ p.name }}</option>
          </select></label
        >
        <label
          >媒体类型<select v-model="preview.identity.kind">
            <option v-for="kind in ['movie', 'tv', 'season', 'episode']" :key="kind" :value="kind">
              {{ labels[kind] }}
            </option>
          </select></label
        >
        <label
          >TMDB ID{{ ['season', 'episode'].includes(preview.identity.kind) ? '（填写整剧 ID）' : ''
          }}<input
            type="number"
            min="1"
            step="1"
            v-model.number="preview.identity.tmdb_id"
            placeholder="例如 12345"
        /></label>
        <label>作品名（可选）<input v-model="preview.identity.title" /></label>
        <label v-if="['season', 'episode'].includes(preview.identity.kind)"
          >季号<input type="number" min="0" step="1" v-model.number="preview.identity.season"
        /></label>
        <label v-if="preview.identity.kind === 'episode'"
          >集号<input type="number" min="1" step="1" v-model.number="preview.identity.episode"
        /></label>
      </div>
      <label class="field-label"
        >NFO 内容<textarea class="xml" v-model="preview.nfo" spellcheck="false" />
      </label>
      <details class="advanced-options">
        <summary>
          高级选项
          <span class="hint"
            >{{ preview.overwrite ? '允许替换本地文字' : '保护本地文字' }} ·
            {{ preview.force ? '绕过缓存' : '使用缓存' }}</span
          >
        </summary>
        <label v-if="['season', 'episode'].includes(preview.identity.kind)" class="field-label"
          >分集组 ID（可选）<input v-model="preview.identity.episode_group"
        /></label>
        <div class="stack">
          <label
            ><input
              type="checkbox"
              v-model="preview.overwrite"
            />本次允许替换无法确认来源的本地文字</label
          ><label><input type="checkbox" v-model="preview.force" />本次绕过译文缓存</label>
        </div>
      </details>
      <p v-if="previewIssue" class="hint">{{ previewIssue }}</p>
      <div class="row between preview-actions">
        <span class="hint"
          >{{
            policy?.mode === 'source_only'
              ? '采用来源译文及繁简转换，不调用云端翻译。'
              : '预览可能产生调用费用，并保存缓存。'
          }}不写入媒体文件。</span
        ><button
          class="primary"
          :disabled="locked || !!previewIssue"
          @click="state.run('正在生成翻译预览…', generate)"
        >
          {{ dirty ? '保存并生成预览' : '生成预览' }}
        </button>
      </div>
    </fieldset>
    <div v-if="state.operation === '正在生成翻译预览…'" class="empty" role="status">
      正在读取来源并生成翻译候选，请稍候…
    </div>
    <section v-if="result" class="preview-results" aria-label="预览结果">
      <div class="section-heading">
        <h3>预览结果</h3>
        <div class="row">
          <span class="badge success">{{ result.changed_fields.length }} 个字段变化</span
          ><span class="badge" :class="{ warning: result.pending_fields.length > 0 }"
            >{{ result.pending_fields.length }} 个待处理</span
          >
        </div>
      </div>
      <p v-if="stale" class="alert warning">
        输入或配置已变更，以下为上次预览结果。重新生成可查看当前结果。
      </p>
      <div v-for="item in comparisons" :key="item.field" class="field-comparison">
        <div class="row between">
          <h4>{{ fieldNames[item.field] || item.field }}</h4>
          <div class="row">
            <span
              class="badge"
              :class="item.status === 'failed' ? 'error' : item.changed ? 'success' : ''"
              >{{ labels[item.status] || item.status }}</span
            ><span v-if="item.cache_hit" class="badge">缓存命中</span>
          </div>
        </div>
        <div class="comparison-grid">
          <div>
            <span class="hint">原内容</span>
            <p>{{ item.before || '（空）' }}</p>
          </div>
          <div :class="{ changed: item.changed }">
            <span class="hint">候选内容</span>
            <p>{{ item.after || '（空）' }}</p>
          </div>
        </div>
        <p v-if="item.message" :class="item.status === 'failed' ? 'error' : 'hint'">
          {{ item.message }}
        </p>
      </div>
      <div class="row end">
        <button @click="state.showDetail('候选 NFO', { nfo: result.nfo })">查看候选 NFO</button
        ><button @click="state.showDetail('翻译输出详情', result)">完整详情</button>
      </div>
    </section>
  </section>
</template>
