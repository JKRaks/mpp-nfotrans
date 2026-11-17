<script setup lang="ts">
import { computed, ref } from 'vue'
import type { Policy } from './types'
import { fieldNames, labels, languages } from './useTranslation'
const props = defineProps<{ policy: Policy }>()
const customLanguage = ref(!['zh-CN', 'zh-TW', 'en-US'].includes(props.policy.target_language))
const target = computed({
  get: () => (customLanguage.value ? 'custom' : props.policy.target_language),
  set: (value: string) => {
    customLanguage.value = value === 'custom'
    if (value !== 'custom') props.policy.target_language = value
  },
})
function moveLanguage(index: number, offset: number) {
  const list = props.policy.fallback_languages
  if (index + offset < 0 || index + offset >= list.length) return
  const [value] = list.splice(index, 1)
  list.splice(index + offset, 0, value)
}
function addLanguage() {
  props.policy.fallback_languages.push(
    Object.keys(languages).find((v) => !props.policy.fallback_languages.includes(v)) || '',
  )
}
</script>
<template>
  <div class="policy-editor">
    <div class="grid">
      <label>策略名称<input v-model="policy.name" placeholder="填写易于识别的名称" /></label>
      <label
        >目标语言<select v-model="target">
          <option value="zh-CN">简体中文</option>
          <option value="zh-TW">繁体中文</option>
          <option value="en-US">英语</option>
          <option value="custom">自定义语言代码</option></select
        ><input
          v-if="customLanguage"
          v-model.trim="policy.target_language"
          aria-label="自定义目标语言代码"
          placeholder="例如 ja-JP"
      /></label>
      <label
        >处理模式<select v-model="policy.mode">
          <option value="translate">缺失时自动翻译</option>
          <option value="source_only">仅来源补齐及繁简转换</option>
        </select></label
      >
      <div class="field-label">
        <span>媒体范围</span>
        <div class="row option-row">
          <label v-for="kind in ['movie', 'tv', 'season', 'episode']" :key="kind"
            ><input type="checkbox" :value="kind" v-model="policy.kinds" />{{ labels[kind] }}</label
          >
        </div>
      </div>
    </div>
    <div class="row option-row">
      <span>翻译字段</span
      ><label v-for="(name, field) in fieldNames" :key="field"
        ><input type="checkbox" :value="field" v-model="policy.fields" />{{ name }}</label
      >
    </div>
    <p v-if="!policy.fields.length || !policy.kinds.length" class="warning">
      请至少选择一个翻译字段和一种媒体类型。
    </p>
    <details class="advanced-options">
      <summary>
        高级选项
        <span class="hint">{{
          policy.fallback_languages.map((v) => languages[v] || v).join(' → ') || '未设置备用语言'
        }}</span>
      </summary>
      <p class="hint">按以下顺序寻找可用原文，再根据处理模式补齐。</p>
      <ol class="language-list">
        <li v-for="(language, index) in policy.fallback_languages" :key="index" class="row">
          <span class="language-order">{{ index + 1 }}</span>
          <input
            v-model.trim="policy.fallback_languages[index]"
            :list="'languages-' + policy.id"
            :aria-label="'第 ' + (index + 1) + ' 个备用语言代码'"
            placeholder="语言代码或 original"
          />
          <span class="hint grow">{{ languages[language] || '自定义语言' }}</span>
          <button
            :disabled="index === 0"
            :aria-label="'上移 ' + (languages[language] || language)"
            @click="moveLanguage(index, -1)"
          >
            ↑
          </button>
          <button
            :disabled="index === policy.fallback_languages.length - 1"
            :aria-label="'下移 ' + (languages[language] || language)"
            @click="moveLanguage(index, 1)"
          >
            ↓
          </button>
          <button class="text-button danger" @click="policy.fallback_languages.splice(index, 1)">
            移除
          </button>
        </li>
      </ol>
      <datalist :id="'languages-' + policy.id">
        <option v-for="(name, code) in languages" :key="code" :value="code">{{ name }}</option>
      </datalist>
      <button class="text-button" @click="addLanguage">＋ 添加备用语言</button>
      <div class="stack">
        <label><input type="checkbox" v-model="policy.chinese_conversion" />允许中文繁简转换</label>
        <label
          ><input
            type="checkbox"
            v-model="policy.prefer_official"
          />来源补齐正式译文后，替换未被手工修改的机器译文</label
        >
      </div>
      <p class="hint">original 表示作品原语言。原始标题、人名、媒体 ID 和季集号不进入翻译。</p>
    </details>
  </div>
</template>
