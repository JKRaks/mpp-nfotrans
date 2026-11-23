<script setup lang="ts">
import { provide, reactive, ref, toRefs } from 'vue'
import type { HostProps } from '../types'
import PluginHeader from '../PluginHeader.vue'
import DetailDialog from '../detail/DetailDialog.vue'
import { useDetail } from '../detail/useDetail'
import { TRANSLATION_KEY, useTranslation } from './useTranslation'
import SettingsTab from './tabs/SettingsTab.vue'
import PoliciesTab from './tabs/PoliciesTab.vue'
import PreviewTab from './tabs/PreviewTab.vue'
import HistoryTab from './tabs/HistoryTab.vue'
const props = defineProps<HostProps & { configView?: boolean }>()
const emit = defineEmits(['close'])
const viewer = useDetail()
const state = reactive(useTranslation(props, viewer))
provide(TRANSLATION_KEY, state)
const {
  cfg,
  settings,
  tab,
  dirty,
  busy,
  locked,
  error,
  notice,
  runtimeError,
  configurationIssue,
  serviceIssue,
  defaultPolicy,
  statusText,
  operation,
} = toRefs(state)
const closing = ref(false)
function close() {
  if (dirty.value) closing.value = true
  else emit('close')
}
</script>

<template>
  <main class="translate-app">
    <PluginHeader :title="configView ? '元数据翻译 - 插件配置' : '元数据翻译'" @close="close" />
    <div class="plugin-content" :aria-busy="busy">
      <div v-if="closing" class="confirm-panel" role="alertdialog" aria-label="未保存的配置">
        <p>有未保存的配置，关闭后将丢失这些修改。</p>
        <div class="row end">
          <button @click="closing = false">继续编辑</button
          ><button class="danger" :disabled="busy" @click="emit('close')">放弃修改并关闭</button>
        </div>
      </div>
      <div v-if="error" role="alert" class="alert error">
        {{ error }} <button class="text-button" @click="error = ''">关闭</button>
      </div>
      <div v-if="notice" role="status" class="alert">
        {{ notice }} <button class="text-button" @click="notice = ''">关闭</button>
      </div>
      <div v-if="runtimeError" role="alert" class="alert warning">
        {{ runtimeError }}
        <button :disabled="busy" @click="state.run('正在刷新状态…', () => state.refresh())">
          刷新状态
        </button>
      </div>
      <template v-if="cfg && settings">
        <div class="status-strip">
          <div role="status" aria-live="polite">
            <strong>{{ statusText }}</strong>
            <p class="hint">
              {{ settings.providers[cfg.active_provider] || '未选择翻译服务' }} · 默认策略：{{
                defaultPolicy?.name || '未设置'
              }}
              · {{ cfg.policies.length }} 条策略
            </p>
          </div>
          <button
            v-if="configurationIssue && tab !== 'policies'"
            class="text-button"
            @click="tab = 'policies'"
          >
            完善策略
          </button>
          <button
            v-else-if="
              serviceIssue && tab !== 'settings' && cfg.policies.some((p) => p.mode === 'translate')
            "
            class="text-button"
            @click="tab = 'settings'"
          >
            配置服务
          </button>
        </div>
        <nav class="page-tabs" aria-label="插件页面">
          <button
            v-for="t in [
              { id: 'settings', name: '服务设置' },
              { id: 'policies', name: '翻译策略' },
              { id: 'preview', name: '翻译预览' },
              { id: 'history', name: '调用记录' },
            ]"
            :key="t.id"
            :disabled="busy"
            :class="{ primary: tab === t.id }"
            :aria-current="tab === t.id ? 'page' : undefined"
            @click="tab = t.id"
          >
            {{ t.name }}
          </button>
        </nav>
        <SettingsTab v-show="tab === 'settings'" />
        <PoliciesTab v-show="tab === 'policies'" />
        <PreviewTab v-show="tab === 'preview'" />
        <HistoryTab v-if="tab === 'history'" />
        <div v-if="tab !== 'history' || dirty" class="config-actions">
          <div class="row">
            <label
              ><input
                type="checkbox"
                role="switch"
                v-model="cfg.enabled"
                :disabled="locked"
              />启用翻译服务</label
            ><span :class="dirty ? 'warning' : 'hint'">{{
              dirty ? '● 有未保存修改' : '✓ 已保存'
            }}</span>
          </div>
          <button
            :class="{ primary: dirty }"
            :disabled="locked || !dirty"
            @click="state.run('正在保存配置…', state.save)"
          >
            {{ operation === '正在保存配置…' ? '正在保存…' : '保存配置' }}
          </button>
        </div>
      </template>
      <div v-else class="empty">
        <p>{{ busy ? '正在读取配置…' : '配置未能加载' }}</p>
        <button v-if="!busy" @click="state.run('正在读取配置…', () => state.refresh(true))">
          重新加载
        </button>
      </div>
    </div>
    <DetailDialog
      v-if="viewer.localSession.value"
      :session="viewer.localSession.value"
      @close="viewer.close"
    />
  </main>
</template>
<style src="./translate.css"></style>
