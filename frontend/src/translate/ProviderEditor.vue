<script setup lang="ts">
import { computed, inject, ref, watch } from 'vue'
import { TRANSLATION_KEY } from './useTranslation'
const props = defineProps<{ id: string }>()
const state = inject(TRANSLATION_KEY)!
const provider = computed(() => state.cfg?.provider_configs[props.id])
const editingKey = ref(false),
  showKey = ref(false)
const savedKey = computed(() => !!state.settings?.secret_set[props.id])
const keyStatus = computed(() =>
  state.secrets[props.id] === null
    ? '待删除，保存后生效'
    : state.secrets[props.id]
      ? '已输入新密钥，尚未保存'
      : savedKey.value
        ? '已保存密钥'
        : '尚未配置密钥',
)
const help: Record<string, string> = {
  deepl: '使用 DeepL API 认证密钥，并选择账户对应的 Free 或 Pro 套餐。',
  siliconflow_hunyuan: '使用硅基流动控制台创建的 API 密钥，默认模型为 tencent/Hunyuan-MT-7B。',
  openrouter: '使用 OpenRouter 的 API Key 和模型 ID，失败后不会自动切换模型或服务。',
  gemini_native: '使用 Google AI Studio 创建的 API Key，此处采用 Gemini 原生 API。',
  chat_completions: '填写同一家兼容服务的 API Key、完整 chat/completions 地址和模型 ID。',
}
watch(
  () => state.settings?.revision,
  () => {
    if (!state.secrets[props.id]) {
      editingKey.value = false
      showKey.value = false
    }
  },
)
function editKey(event: Event) {
  const value = (event.target as HTMLInputElement).value.trim()
  if (value) state.secrets[props.id] = value
  else delete state.secrets[props.id]
}
function removeKey() {
  if (savedKey.value) state.secrets[props.id] = null
  else delete state.secrets[props.id]
  editingKey.value = false
  showKey.value = false
}
function cancelKey() {
  delete state.secrets[props.id]
  editingKey.value = false
  showKey.value = false
}
</script>
<template>
  <div v-if="provider" class="provider-editor">
    <div class="key-section">
      <div class="row between">
        <label :for="'key-' + id">API Key</label
        ><span class="hint" role="status">{{ keyStatus }}</span>
      </div>
      <div v-if="state.secrets[id] === null" class="row key-row">
        <span class="warning grow">保存后将移除该服务的密钥。</span
        ><button @click="delete state.secrets[id]">撤销删除</button>
      </div>
      <div v-else-if="savedKey && !editingKey && !state.secrets[id]" class="row key-row">
        <input
          :id="'key-' + id"
          class="grow"
          value="••••••••••••"
          readonly
          aria-label="已保存的密钥不会回显"
        />
        <button @click="editingKey = true">更换密钥</button
        ><button class="text-button danger" @click="removeKey">删除密钥</button>
      </div>
      <div v-else class="row key-row">
        <input
          :id="'key-' + id"
          class="grow"
          :type="showKey ? 'text' : 'password'"
          :value="state.secrets[id] || ''"
          @input="editKey"
          autocomplete="new-password"
          spellcheck="false"
          :placeholder="savedKey ? '留空保留已保存的密钥' : '粘贴此服务的 API Key'"
        />
        <button :aria-pressed="showKey" @click="showKey = !showKey">
          {{ showKey ? '隐藏输入' : '显示输入' }}
        </button>
        <button v-if="savedKey || state.secrets[id]" class="text-button" @click="cancelKey">
          取消输入
        </button>
      </div>
    </div>
    <div class="grid">
      <label v-if="id === 'deepl'"
        >DeepL 套餐<select v-model="provider.deepl_plan">
          <option value="free">API Free</option>
          <option value="pro">API Pro</option>
        </select></label
      >
      <template v-else
        ><label
          >模型 ID<input v-model.trim="provider.model" placeholder="填写准确模型标识"
        /></label>
        <label
          >服务地址<input
            v-model.trim="provider.endpoint"
            :placeholder="
              id === 'gemini_native'
                ? 'https://generativelanguage.googleapis.com'
                : '完整 chat/completions 地址'
            " /></label
      ></template>
    </div>
    <details class="advanced-options">
      <summary>
        高级参数
        <span class="hint"
          >{{ provider.max_chars }} 字符<template v-if="id !== 'deepl'">
            · {{ provider.max_output_tokens }} 输出 token</template
          ></span
        >
      </summary>
      <div class="grid">
        <label v-if="id === 'gemini_native'"
          >API 版本<select v-model="provider.api_version">
            <option>v1beta</option>
            <option>v1</option>
          </select></label
        >
        <label v-if="!['deepl', 'siliconflow_hunyuan'].includes(id)"
          >响应模式<select v-model="provider.response_mode">
            <option value="prompt_json">提示词约束 JSON</option>
            <option value="json_object">JSON Object</option>
            <option value="json_schema">JSON Schema</option>
          </select></label
        >
        <label
          >每次文本字符上限<input
            type="number"
            min="100"
            max="100000"
            v-model.number="provider.max_chars"
        /></label>
        <label v-if="id !== 'deepl'"
          >最大输出 token<input
            type="number"
            min="128"
            max="32768"
            v-model.number="provider.max_output_tokens"
        /></label>
      </div>
      <p v-if="id === 'siliconflow_hunyuan'" class="hint">
        Hunyuan-MT 使用单段纯文本翻译，不发送 JSON 输出要求。
      </p>
    </details>
    <details class="help-details">
      <summary>服务与密钥填写说明</summary>
      <p>{{ help[id] }}</p>
      <p>
        仅填写密钥本身，不添加 Bearer、Authorization
        或引号。已保存的密钥不会回显；更换和删除均在保存配置后生效。
      </p>
    </details>
  </div>
</template>
