<script setup lang="ts">
import { computed, inject, ref, toRefs, watch } from 'vue'
import { TRANSLATION_KEY, messageOf } from '../useTranslation'
import type { FieldResult } from '../types'
import ProviderEditor from '../ProviderEditor.vue'
const state = inject(TRANSLATION_KEY)!
const { cfg, settings, dirty, locked, serviceIssue, configurationIssue } = toRefs(state)
const connection = ref<{ ok: boolean; message: string }>()
const cacheToClear = ref('')
const signature = computed(() =>
  JSON.stringify([
    cfg.value?.active_provider,
    cfg.value?.provider_configs[cfg.value?.active_provider || ''],
    cfg.value?.timeout,
    settings.value?.revision,
    state.secrets[cfg.value?.active_provider || ''],
  ]),
)
watch(signature, () => {
  connection.value = undefined
})
const otherProviders = computed(() =>
  Object.entries(settings.value?.providers || {}).filter(
    ([id]) => id !== cfg.value?.active_provider,
  ),
)
async function checkConnection() {
  connection.value = undefined
  try {
    await state.save()
    const result = await state.api.post<{ sample?: FieldResult }>(state.url('test'))
    const sample = result.sample
    connection.value = {
      ok: sample?.status === 'translated',
      message:
        sample?.status === 'translated'
          ? '连接成功，示例译文：' + sample.text
          : sample?.message || '连接未成功，请检查服务配置',
    }
  } catch (cause) {
    connection.value = { ok: false, message: messageOf(cause) }
  }
}
async function clearCache() {
  const kind = cacheToClear.value
  if (!kind) return
  await state.api.post(state.url('cache/clear'), { kind })
  cacheToClear.value = ''
  state.notice = '缓存已清理，媒体文件和调用记录保留'
}
</script>
<template>
  <section v-if="cfg && settings" aria-label="服务设置">
    <details class="settings-section" open>
      <summary>
        <strong>当前翻译服务</strong
        ><span v-if="connection?.ok" class="badge success">连接已验证</span
        ><span v-else class="hint">{{ serviceIssue ? '待配置' : '配置完整，尚未验证连接' }}</span>
      </summary>
      <fieldset class="settings-body" :disabled="locked">
        <label class="field-label"
          >翻译服务<select v-model="cfg.active_provider">
            <option value="">请选择服务</option>
            <option v-for="(name, id) in settings.providers" :key="id" :value="id">
              {{ name }}
            </option>
          </select></label
        >
        <ProviderEditor
          v-if="cfg.active_provider"
          :key="cfg.active_provider"
          :id="cfg.active_provider"
        />
        <p v-else class="hint">需要自动翻译时，先选择一家服务；仅来源补齐可直接配置策略。</p>
        <p v-if="serviceIssue && cfg.active_provider" class="warning">{{ serviceIssue }}</p>
        <div class="row between service-actions">
          <span class="hint">连接检查发送固定示例，可能产生调用费用。</span>
          <button
            class="primary"
            :disabled="!cfg.enabled || !!serviceIssue || !!configurationIssue"
            @click="state.run('正在检查连接…', checkConnection)"
          >
            {{ dirty ? '保存并检查连接' : '检查连接' }}
          </button>
        </div>
        <p v-if="!cfg.enabled" class="hint">启用翻译服务后可检查连接。</p>
        <p v-if="connection" role="status" :class="connection.ok ? 'success' : 'error'">
          {{ connection.message }}
        </p>
      </fieldset>
    </details>
    <p v-if="settings.hook_conflicts.length" class="alert warning">
      检测到其他 NFO 扩展：{{ settings.hook_conflicts.join('、') }}。官方刮削增强暂停，NfoCheck
      显式翻译仍可使用。
    </p>
    <details class="settings-section">
      <summary>
        <strong>官方刮削增强</strong
        ><span>{{
          cfg.global_hook ? (settings.hook_conflicts.length ? '冲突暂停' : '已开启') : '已关闭'
        }}</span>
      </summary>
      <fieldset class="settings-body" :disabled="locked">
        <label><input type="checkbox" v-model="cfg.global_hook" />增强官方 NFO 刮削</label>
        <label class="field-label"
          >官方刮削默认策略<select v-model="cfg.default_policy">
            <option v-for="p in cfg.policies" :key="p.id" :value="p.id">{{ p.name }}</option>
          </select></label
        >
        <p class="hint">
          补齐以后刮削生成的 NFO。已有媒体的修复、备份和 Emby 同步在 NfoCheck 中执行。
        </p>
      </fieldset>
    </details>
    <details class="settings-section">
      <summary>
        <strong>请求与缓存</strong
        ><span
          >{{ cfg.timeout }} 秒超时 · 并发 {{ cfg.concurrency }} · 译文
          {{ settings.cache.translation || 0 }} 条</span
        >
      </summary>
      <fieldset class="settings-body" :disabled="locked">
        <div class="grid">
          <label
            >单次时限（秒）<input type="number" min="5" max="120" v-model.number="cfg.timeout"
          /></label>
          <label
            >并发数<input type="number" min="1" max="8" v-model.number="cfg.concurrency"
          /></label>
          <label
            >来源缓存（小时）<input
              type="number"
              min="1"
              max="720"
              v-model.number="cfg.source_hours"
          /></label>
          <label
            >无原文复查间隔（天）<input
              type="number"
              min="1"
              max="365"
              v-model.number="cfg.missing_days"
          /></label>
          <label
            >译文缓存（天）<input type="number" min="1" max="3650" v-model.number="cfg.cache_days"
          /></label>
          <label
            >调用记录保留（天）<input
              type="number"
              min="1"
              max="3650"
              v-model.number="cfg.history_days"
          /></label>
        </div>
        <div class="row">
          <span class="hint"
            >来源 {{ settings.cache.source || 0 }} 条 · 译文
            {{ settings.cache.translation || 0 }} 条</span
          >
          <button @click="cacheToClear = 'source'">清理来源缓存</button
          ><button @click="cacheToClear = 'translation'">清理译文缓存</button>
        </div>
        <div v-if="cacheToClear" class="confirm-panel" role="alertdialog" aria-label="清理缓存">
          <p>
            清理全部{{
              cacheToClear === 'source' ? '来源' : '译文'
            }}缓存？下次使用时将重新请求服务。
          </p>
          <div class="row end">
            <button @click="cacheToClear = ''">取消</button
            ><button class="danger" @click="state.run('正在清理缓存…', clearCache)">
              确认清理
            </button>
          </div>
        </div>
      </fieldset>
    </details>
    <details class="settings-section">
      <summary><strong>其他服务配置</strong><span>管理已保存的服务</span></summary>
      <div class="settings-body">
        <p class="hint">这里的编辑不会切换当前服务。需要使用时，在上方“翻译服务”中选择。</p>
        <details v-for="[id, name] in otherProviders" :key="id" class="settings-section nested">
          <summary>
            <strong>{{ name }}</strong
            ><span>{{
              state.secrets[id] === null
                ? '密钥待删除'
                : state.secrets[id]
                  ? '密钥待保存'
                  : settings.secret_set[id]
                    ? '已保存密钥'
                    : '尚未配置密钥'
            }}</span>
          </summary>
          <fieldset class="settings-body" :disabled="locked"><ProviderEditor :id="id" /></fieldset>
        </details>
      </div>
    </details>
    <details class="help-details">
      <summary>翻译服务如何使用？</summary>
      <p>
        所有策略共用当前服务，失败后不会自动切换服务或模型。先配置服务，再选择翻译策略，最后生成预览确认结果。
      </p>
    </details>
  </section>
</template>
