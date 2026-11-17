<script setup lang="ts">
import { inject, ref, toRefs } from 'vue'
import { TRANSLATION_KEY, fieldNames, labels, languages } from '../useTranslation'
import type { Policy } from '../types'
import PolicyEditor from '../PolicyEditor.vue'
const state = inject(TRANSLATION_KEY)!
const { cfg, locked, configurationIssue } = toRefs(state)
const expanded = ref(cfg.value?.default_policy || ''),
  templates = ref(false),
  deletion = ref<Policy>(),
  replacement = ref('')
function create(template = 'custom', source?: Policy) {
  if (!cfg.value) return
  const policy: Policy = source
    ? {
        ...JSON.parse(JSON.stringify(source)),
        id: crypto.randomUUID(),
        name: source.name + '（副本）',
      }
    : {
        id: crypto.randomUUID(),
        name:
          template === 'traditional'
            ? '繁体中文补全'
            : template === 'source'
              ? '仅来源补齐'
              : template === 'simplified'
                ? '简体中文补全'
                : '新翻译策略',
        target_language: template === 'traditional' ? 'zh-TW' : 'zh-CN',
        fields: ['plot', 'outline'],
        kinds: ['movie', 'tv', 'season', 'episode'],
        mode: template === 'source' ? 'source_only' : 'translate',
        fallback_languages: [template === 'traditional' ? 'zh-CN' : 'zh-TW', 'en-US', 'original'],
        chinese_conversion: true,
        prefer_official: true,
      }
  cfg.value.policies.push(policy)
  if (cfg.value.policies.length === 1) cfg.value.default_policy = policy.id
  expanded.value = policy.id
  templates.value = false
}
function summary(policy: Policy) {
  return [
    languages[policy.target_language] || policy.target_language,
    policy.fields.map((v) => fieldNames[v] || v).join('、') || '未选择字段',
    policy.kinds.length === 4
      ? '全部媒体'
      : policy.kinds.map((v) => labels[v]).join('、') || '未选择媒体',
    policy.mode === 'translate' ? '缺失时翻译' : '不调用翻译服务',
  ].join(' · ')
}
function askDelete(policy: Policy) {
  deletion.value = policy
  replacement.value = cfg.value?.policies.find((p) => p.id !== policy.id)?.id || ''
}
function remove() {
  if (!cfg.value || !deletion.value || cfg.value.policies.length < 2) return
  const id = deletion.value.id
  if (id === cfg.value.default_policy) {
    if (!cfg.value.policies.some((p) => p.id === replacement.value && p.id !== id)) return
    cfg.value.default_policy = replacement.value
  }
  cfg.value.policies = cfg.value.policies.filter((p) => p.id !== id)
  if (expanded.value === id) expanded.value = ''
  deletion.value = undefined
}
</script>
<template>
  <section v-if="cfg" aria-label="翻译策略">
    <div class="section-heading">
      <h3>翻译策略</h3>
      <div class="row">
        <button :disabled="locked" :aria-expanded="templates" @click="templates = !templates">
          从模板添加</button
        ><button class="primary" :disabled="locked" @click="create()">新建策略</button>
      </div>
    </div>
    <div v-if="templates" class="template-picker">
      <p class="hint">选择一个起点，创建后可继续调整字段、范围和备用语言。</p>
      <div class="template-options">
        <button :disabled="locked" @click="create('simplified')">
          <strong>简体中文补全</strong><span>补齐简体中文简介与摘要</span>
        </button>
        <button :disabled="locked" @click="create('traditional')">
          <strong>繁体中文补全</strong><span>补齐繁体中文简介与摘要</span>
        </button>
        <button :disabled="locked" @click="create('source')">
          <strong>仅来源补齐</strong><span>采用来源译文或本地繁简转换</span>
        </button>
      </div>
    </div>
    <p v-if="configurationIssue" class="warning" role="status">{{ configurationIssue }}</p>
    <fieldset
      v-for="policy in cfg.policies"
      :key="policy.id"
      class="policy-card"
      :disabled="locked"
    >
      <div class="policy-heading">
        <button
          class="disclosure"
          :aria-expanded="expanded === policy.id"
          :aria-controls="'policy-' + policy.id"
          @click="expanded = expanded === policy.id ? '' : policy.id"
        >
          <span class="disclosure-marker" aria-hidden="true"></span
          ><strong>{{ policy.name || '未命名策略' }}</strong>
        </button>
        <span v-if="policy.id === cfg.default_policy" class="badge active">默认</span>
        <span class="policy-summary" :title="summary(policy)">{{ summary(policy) }}</span>
        <details class="more-menu">
          <summary :aria-label="policy.name + '的操作'">⋯</summary>
          <div
            class="menu-actions"
            @click="($event.currentTarget as HTMLElement).parentElement?.removeAttribute('open')"
          >
            <button @click="expanded = policy.id">编辑策略</button
            ><button @click="create('custom', policy)">复制策略</button>
            <button
              :disabled="policy.id === cfg.default_policy"
              @click="cfg.default_policy = policy.id"
            >
              设为默认
            </button>
            <button class="danger" :disabled="cfg.policies.length < 2" @click="askDelete(policy)">
              删除策略
            </button>
          </div>
        </details>
      </div>
      <div
        v-if="deletion?.id === policy.id"
        class="confirm-panel inset"
        role="alertdialog"
        aria-label="删除翻译策略"
      >
        <p>删除「{{ policy.name }}」？保存配置后生效。NfoCheck 中引用该策略的规则需要另行调整。</p>
        <label v-if="policy.id === cfg.default_policy" class="field-label"
          >新的默认策略<select v-model="replacement">
            <option
              v-for="p in cfg.policies.filter((p) => p.id !== policy.id)"
              :key="p.id"
              :value="p.id"
            >
              {{ p.name }}
            </option>
          </select></label
        >
        <div class="row end">
          <button @click="deletion = undefined">取消</button
          ><button class="danger" @click="remove">确认删除</button>
        </div>
      </div>
      <PolicyEditor v-if="expanded === policy.id" :id="'policy-' + policy.id" :policy="policy" />
    </fieldset>
    <div v-if="!cfg.policies.length" class="empty">
      <p>从模板创建第一条翻译策略。</p>
      <button class="primary" :disabled="locked" @click="templates = true">选择模板</button>
    </div>
    <details class="help-details">
      <summary>策略如何使用？</summary>
      <p>
        默认策略用于官方刮削增强；预览和 NfoCheck
        可分别选择策略。所有策略共用当前翻译服务，至少保留一条策略。
      </p>
    </details>
  </section>
</template>
