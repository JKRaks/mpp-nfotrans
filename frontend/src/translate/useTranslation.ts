import { computed, onMounted, onUnmounted, ref, shallowRef } from 'vue'
import type { InjectionKey, UnwrapNestedRefs } from 'vue'
import type { HostProps } from '../types'
import type { useDetail } from '../detail/useDetail'
import type { Settings, TranslationConfig } from './types'

export const languages: Record<string, string> = {
  'zh-CN': '简体中文',
  'zh-TW': '繁体中文',
  'en-US': '英语',
  original: '作品原语言',
}
export const labels: Record<string, string> = {
  movie: '电影',
  tv: '整剧',
  season: '季',
  episode: '单集',
  translated: '已翻译',
  official: '采用来源译文',
  converted: '繁简转换',
  kept: '已有目标语言',
  not_applicable: '不适用',
  protected: '保护本地修改',
  language_unknown: '语言待确认',
  no_source_text: '没有可用原文',
  failed: '失败',
  complete: '候选已完成',
  partial: '部分完成',
}
export const fieldNames: Record<string, string> = {
  title: '标题',
  plot: '剧情简介',
  outline: '简短摘要',
  tagline: '宣传语',
}
export function messageOf(error: unknown) {
  const value = error as { response?: { data?: { detail?: unknown } }; message?: string }
  const detail = value?.response?.data?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) return detail.map((item) => item.msg || '配置格式无效').join('；')
  return (detail as { message?: string })?.message || value?.message || '操作失败，请重试'
}

export function useTranslation(host: HostProps, viewer: ReturnType<typeof useDetail>) {
  const cfg = ref<TranslationConfig>(),
    settings = shallowRef<Settings>()
  const secrets = ref<Record<string, string | null>>({}),
    saved = ref('')
  const tab = ref('settings'),
    operation = ref(''),
    error = ref(''),
    notice = ref('')
  const runtimeError = ref('')
  let disposed = false,
    timer: ReturnType<typeof setTimeout> | undefined,
    request = 0
  const api = host.api,
    url = (path: string) => `plugin/${host.pluginId}/${path}`
  const secretChanges = computed(() =>
    Object.fromEntries(
      Object.entries(secrets.value).filter(([id, value]) =>
        value === null ? !!settings.value?.secret_set[id] : !!value?.trim(),
      ),
    ),
  )
  const dirty = computed(
    () =>
      !!cfg.value &&
      (JSON.stringify(cfg.value) !== saved.value || Object.keys(secretChanges.value).length > 0),
  )
  const busy = computed(() => !!operation.value)
  const locked = computed(() => busy.value || !!settings.value?.busy || !!runtimeError.value)
  const defaultPolicy = computed(() =>
    cfg.value?.policies.find((p) => p.id === cfg.value?.default_policy),
  )
  const configurationIssue = computed(() => {
    if (!cfg.value) return ''
    if (!defaultPolicy.value) return '请选择一个默认策略'
    for (const policy of cfg.value.policies) {
      if (!policy.name.trim()) return '请填写策略名称'
      if (!policy.fields.length) return `「${policy.name}」需要选择翻译字段`
      if (!policy.kinds.length) return `「${policy.name}」需要选择媒体范围`
      const locale = /^[a-z]{2,3}(?:[-_][A-Za-z0-9]{2,8})*$/i
      if (!locale.test(policy.target_language.trim())) return `「${policy.name}」的目标语言代码无效`
      if (policy.fallback_languages.some((v) => v !== 'original' && !locale.test(v.trim())))
        return `「${policy.name}」的备用语言代码无效`
    }
    return ''
  })
  const serviceIssue = computed(() => {
    const id = cfg.value?.active_provider
    if (!id) return '请选择当前翻译服务'
    const provider = cfg.value?.provider_configs[id]
    if (!provider) return '当前服务配置不存在'
    const key = secrets.value[id]
    if (key === null || !(key || settings.value?.secret_set[id])) return '请填写当前服务的 API Key'
    if (id !== 'deepl' && !provider.endpoint.trim()) return '请填写当前服务的地址'
    if (id !== 'deepl' && !provider.model.trim()) return '请填写当前服务的模型 ID'
    return ''
  })
  const statusText = computed(() => {
    if (operation.value) return operation.value
    if (runtimeError.value) return '运行状态暂不可用'
    if (settings.value?.busy) return '翻译任务运行中，结束后可保存配置'
    if (dirty.value) return '有未保存修改，保存后生效'
    if (!cfg.value?.enabled) return '翻译服务未启用'
    if (configurationIssue.value) return configurationIssue.value
    if (cfg.value.policies.some((p) => p.mode === 'translate') && serviceIssue.value)
      return serviceIssue.value
    return '服务已就绪，可以生成翻译预览'
  })

  async function refresh(reset = false) {
    const id = ++request
    const data = await api.get<Settings>(url('settings'))
    if (disposed || id !== request) return
    settings.value = data
    runtimeError.value = ''
    if (reset || !cfg.value) {
      cfg.value = JSON.parse(JSON.stringify(data.config))
      saved.value = JSON.stringify(cfg.value)
    }
  }
  async function save() {
    if (!cfg.value || !dirty.value) return
    if (settings.value?.busy || runtimeError.value)
      throw new Error('请等待任务结束或刷新运行状态后保存')
    if (configurationIssue.value) {
      tab.value = 'policies'
      throw new Error(configurationIssue.value)
    }
    const config = JSON.parse(JSON.stringify(cfg.value)) as TranslationConfig
    const changes = { ...secretChanges.value }
    await api.post(url('settings'), { config, secrets: changes })
    saved.value = JSON.stringify(config)
    secrets.value = {}
    if (settings.value) {
      const secret_set = { ...settings.value.secret_set }
      for (const [id, value] of Object.entries(changes)) secret_set[id] = !!value
      settings.value = { ...settings.value, config, secret_set }
    }
    await refresh(true)
    notice.value = '配置已保存'
  }
  async function run(name: string, action: () => Promise<unknown>) {
    if (busy.value) return
    operation.value = name
    error.value = ''
    notice.value = ''
    try {
      await action()
    } catch (cause) {
      error.value = messageOf(cause)
    } finally {
      try {
        await refresh()
      } catch (cause) {
        runtimeError.value = messageOf(cause)
      }
      operation.value = ''
    }
  }
  async function poll() {
    try {
      if (!busy.value) await refresh()
    } catch (cause) {
      if (!disposed) runtimeError.value = messageOf(cause)
    } finally {
      if (!disposed) timer = setTimeout(poll, 10000)
    }
  }
  onMounted(() => {
    void run('正在读取配置…', () => refresh(true)).then(() => {
      if (!disposed) timer = setTimeout(poll, 10000)
    })
  })
  onUnmounted(() => {
    disposed = true
    request++
    clearTimeout(timer)
  })
  return {
    cfg,
    settings,
    secrets,
    dirty,
    busy,
    locked,
    tab,
    operation,
    error,
    notice,
    runtimeError,
    defaultPolicy,
    configurationIssue,
    serviceIssue,
    statusText,
    api,
    url,
    refresh,
    save,
    run,
    showDetail: viewer.show,
    closeDetail: viewer.close,
  }
}
export const TRANSLATION_KEY: InjectionKey<UnwrapNestedRefs<ReturnType<typeof useTranslation>>> =
  Symbol('translation')
