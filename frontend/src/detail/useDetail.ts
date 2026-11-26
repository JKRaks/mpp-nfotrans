import {computed, inject, nextTick, onBeforeUnmount, shallowReactive, shallowRef} from 'vue'
import type {Component} from 'vue'
import DetailDialog from './DetailDialog.vue'

export interface DetailSession {
  title: string
  subtitle: string
  data?: unknown
  loading?: boolean
  error?: string
}

type OpenHostDialog = (
  component: Component,
  props: Record<string, unknown>,
  events: { close: () => void },
  options: { closeOn: false },
) => { close: () => void }

export function useDetail() {
  const openHostDialog = inject<OpenHostDialog | null>('moviepilot:dialog', null)
  const active = shallowRef<DetailSession | null>(null)
  const localSession = computed(() => openHostDialog ? null : active.value)
  let hostDialog: ReturnType<OpenHostDialog> | undefined
  let trigger: HTMLElement | null = null

  function close() {
    const returnTo = trigger
    trigger = null
    active.value = null
    hostDialog?.close()
    hostDialog = undefined
    void nextTick(() => {
      if (!active.value && returnTo?.isConnected) returnTo.focus({preventScroll: true})
    })
  }

  function open(content: DetailSession) {
    const focused = document.activeElement
    const returnTo = active.value ? trigger : focused instanceof HTMLElement ? focused : null
    close()
    trigger = returnTo
    const session = shallowReactive(content)
    active.value = session
    if (openHostDialog) {
      hostDialog = openHostDialog(DetailDialog, {session}, {
        close: () => { if (active.value === session) close() },
      }, {closeOn: false})
    }
    return session
  }

  async function show(title: string, value: unknown | (() => Promise<unknown>), subtitle = '') {
    const session = open({title, subtitle, loading: typeof value === 'function'})
    try {
      const result = typeof value === 'function' ? await value() : value
      if (active.value === session) session.data = result
    } catch (error: any) {
      if (active.value === session) {
        const detail = error?.response?.data?.detail
        session.error = typeof detail === 'string' ? detail : error?.message || '详情读取失败'
      }
    } finally {
      if (active.value === session) session.loading = false
    }
  }

  onBeforeUnmount(close)
  return {localSession, show, close}
}
