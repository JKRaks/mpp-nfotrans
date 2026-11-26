<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import DetailValue from './DetailValue.vue'
import { catalog, displayValue, fieldLabel } from './labels'

const props = defineProps<{ data: unknown }>()
const emit = defineEmits<{ (event: 'navigate'): void }>()
const mode = ref('formatted')
const selected = ref('')
watch(() => props.data, () => { mode.value = 'formatted'; selected.value = '' })
watch([mode, selected], () => emit('navigate'))
const knownFields = new Map(catalog.map(field => [field.value, field]))
function record(value: unknown): value is Record<string, unknown> {
  return !!value && typeof value === 'object' && !Array.isArray(value)
}
const data = computed(() => record(props.data) ? props.data : {})
const xml = computed(() => typeof data.value.nfo === 'string' ? data.value.nfo : null)
const hasMetadata = computed(() => xml.value === null || Object.keys(data.value).some(key => key !== 'nfo'))
const original = computed(() => mode.value === 'xml' ? xml.value : JSON.stringify(props.data, null, 2))
type Section = { id: string; label: string; value?: unknown; nodes?: Element[]; field?: boolean }

const parsed = computed<{ sections: Section[]; error?: string }>(() => {
  if (xml.value === null) return { sections: [] }
  if (/<!DOCTYPE|<!ENTITY/i.test(xml.value))
    return { sections: [], error: '含实体声明，无法格式化。可以查看原始 XML。' }
  const doc = new DOMParser().parseFromString(xml.value, 'application/xml')
  if (doc.getElementsByTagName('parsererror').length)
    return { sections: [], error: 'XML 格式有误，可以查看原始 XML。' }
  const groups = new Map<string, Element[]>()
  for (const node of Array.from(doc.documentElement.children)) {
    const label = knownFields.get(node.tagName)?.group || '其他字段'
    if (!groups.has(label)) groups.set(label, [])
    groups.get(label)!.push(node)
  }
  return { sections: Array.from(groups, ([label, nodes]) => ({ id: 'nfo:' + label, label: 'NFO · ' + label, nodes })) }
})

function nodeValue(node: Element, depth = 0): unknown {
  if (depth > 20) return node.textContent || ''
  const fields: Record<string, unknown> = Object.create(null)
  for (const attr of Array.from(node.attributes)) fields['@' + attr.name] = attr.value
  if (!node.children.length)
    return node.attributes.length ? { ...fields, text: node.textContent || '' } : node.textContent || ''
  for (const child of Array.from(node.children)) {
    const value = nodeValue(child, depth + 1)
    const key = child.tagName
    if (!(key in fields)) fields[key] = value
    else if (Array.isArray(fields[key])) fields[key].push(value)
    else fields[key] = [fields[key], value]
  }
  return fields
}

const sections = computed<Section[]>(() => {
  const groups: Section[] = []
  const { nfo, fields, sample, identity, provenance, ...rest } = data.value
  if (record(fields)) {
    for (const [key, value] of Object.entries(fields))
      groups.push({ id: 'field:' + key, label: fieldLabel(key), value, field: true })
  } else if (fields !== undefined) groups.push({ id: 'fields', label: '字段结果', value: fields })
  // Connection checks store a sample result instead of NFO field results.
  if (sample !== undefined) groups.push({ id: 'sample', label: '连接检查', value: sample, field: true })
  groups.push(...parsed.value.sections)
  if (identity !== undefined) groups.push({ id: 'identity', label: '媒体身份', value: identity })
  if (Object.keys(rest).length) groups.push({ id: 'record', label: '处理记录', value: rest })
  if (provenance !== undefined) groups.push({ id: 'provenance', label: '来源记录', value: provenance })
  if (!record(props.data) && props.data != null) groups.push({ id: 'content', label: '内容', value: props.data })
  return groups
})
const active = computed(() => sections.value.find(group => group.id === selected.value) ?? sections.value[0])
const rows = computed(() => active.value?.nodes?.map(node => ({ label: fieldLabel(node.tagName), value: nodeValue(node) })))
const fieldResult = computed(() => active.value?.field && record(active.value.value) ? active.value.value : null)
const comparison = computed(() => {
  const result = fieldResult.value
  if (!result) return []
  return [
    { key: 'before', label: '原有内容' },
    { key: 'text', label: '候选内容' },
    { key: 'source_text', label: '来源原文' },
  ].filter(item => result[item.key] !== undefined).map(item => ({ ...item, value: result[item.key] }))
})
const fieldInfo = computed(() => {
  if (!fieldResult.value) return {}
  const { before, text, source_text, status, message, ...rest } = fieldResult.value
  return rest
})
</script>

<template>
  <div class="readout">
    <div class="view-options" role="group" aria-label="显示方式">
      <button type="button" :aria-pressed="mode === 'formatted'" @click="mode = 'formatted'">格式化查看</button>
      <button v-if="hasMetadata" type="button" :aria-pressed="mode === 'raw'" @click="mode = 'raw'">原始数据</button>
      <button v-if="xml !== null" type="button" :aria-pressed="mode === 'xml'" @click="mode = 'xml'">原始 XML</button>
    </div>
    <pre v-if="mode !== 'formatted'" class="raw">{{ original }}</pre>
    <template v-else>
      <p v-if="parsed.error" class="error" role="alert">{{ parsed.error }}</p>
      <div v-if="active" class="groups" :class="{ multiple: sections.length > 1 }">
        <template v-if="sections.length > 1">
          <nav aria-label="详情分组">
            <button v-for="group in sections" :key="group.id" type="button"
                    :aria-current="active.id === group.id ? 'true' : undefined"
                    @click="selected = group.id">{{ group.label }}</button>
          </nav>
          <label class="group-picker">查看分组
            <select :value="active.id" @change="selected = ($event.target as HTMLSelectElement).value">
              <option v-for="group in sections" :key="group.id" :value="group.id">{{ group.label }}</option>
            </select>
          </label>
        </template>
        <section class="group-content" :aria-label="active.label">
          <h3>{{ active.label }}</h3>
          <template v-if="fieldResult">
            <div v-if="fieldResult.status || fieldResult.message" class="summary">
              <span v-if="fieldResult.status" class="status-label" :class="{ error: fieldResult.status === 'failed' }">{{ displayValue(fieldResult.status, 'status') }}</span>
              <p v-if="fieldResult.message">{{ fieldResult.message }}</p>
            </div>
            <div v-if="comparison.length" class="comparison">
              <div v-for="item in comparison" :key="item.key" :class="{ source: item.key === 'source_text' }">
                <h4>{{ item.label }}</h4>
                <DetailValue :value="item.value" />
              </div>
            </div>
            <DetailValue v-if="Object.keys(fieldInfo).length" :value="fieldInfo" />
          </template>
          <dl v-else-if="rows" class="nfo-values">
            <div v-for="(row, index) in rows" :key="index">
              <dt>{{ row.label }}</dt>
              <dd><DetailValue :value="row.value" /></dd>
            </div>
          </dl>
          <DetailValue v-else :value="active.value" />
        </section>
      </div>
      <p v-else-if="!parsed.error">没有更多详情。</p>
    </template>
  </div>
</template>

<style scoped>
.readout { padding: 16px 20px 22px; min-width: 0; }
.readout * { box-sizing: border-box; }
button, select { font: inherit; color: inherit; cursor: pointer; }
button:focus-visible, select:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
.view-options { display: flex; width: fit-content; flex-wrap: wrap; max-width: 100%; margin: 6px 0 16px; padding: 2px; border: 1px solid var(--line); border-radius: 7px; gap: 2px; }
.view-options button { padding: 6px 10px; border: 0; background: transparent; border-radius: 4px; }
.view-options button[aria-pressed=true], nav button[aria-current=true] { background: var(--tint); color: var(--accent); font-weight: 600; }
.groups.multiple { display: grid; grid-template-columns: minmax(130px, 24%) minmax(0, 1fr); gap: 16px; align-items: start; }
nav { position: sticky; top: 0; display: flex; flex-direction: column; gap: 2px; padding-inline-end: 10px; border-inline-end: 1px solid var(--line); }
nav button { padding: 8px; text-align: start; border: 0; border-radius: 4px; background: transparent; overflow-wrap: anywhere; }
.group-picker { display: none; }
.group-content { min-width: 0; }
.group-content h3 { margin: 0 0 8px; font-size: 16px; overflow-wrap: anywhere; }
.summary { display: flex; flex-wrap: wrap; align-items: baseline; gap: 8px; margin-bottom: 12px; }
.summary p { margin: 0; overflow-wrap: anywhere; }
.status-label { padding: 2px 8px; border-radius: 4px; color: var(--accent); background: var(--tint); }
.comparison { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }
.comparison > div { min-width: 0; padding: 12px; border: 1px solid var(--line); border-radius: 6px; }
.comparison .source, .comparison > div:only-child { grid-column: 1 / -1; }
.comparison h4 { margin: 0 0 6px; color: var(--muted); font-size: 13px; font-weight: 500; }
.nfo-values, .nfo-values dd { margin: 0; }
.nfo-values > div { padding: 8px 0; border-top: 1px solid var(--line); }
.nfo-values dt { color: var(--muted); overflow-wrap: anywhere; font-size: 13px; margin-bottom: 4px; }
.raw { margin: 0; max-width: 100%; padding: 12px; border-radius: 6px; background: var(--tint); white-space: pre-wrap; overflow-wrap: anywhere; font: 13px/1.6 monospace; }
.error { color: rgb(var(--v-theme-error, 169, 41, 49)); }
@media (max-width: 700px) {
  .readout { padding: 12px 14px 20px; }
  .groups.multiple { display: block; }
  nav { display: none; }
  .group-picker { display: flex; gap: 10px; align-items: center; margin-bottom: 14px; }
  .group-picker select { flex: 1; min-width: 0; padding: 8px; border: 1px solid var(--line); border-radius: 6px; background: rgb(var(--v-theme-surface, 255, 255, 255)); appearance: auto; }
  .readout button { min-height: 40px; }
  .comparison { grid-template-columns: minmax(0, 1fr); }
}
</style>
