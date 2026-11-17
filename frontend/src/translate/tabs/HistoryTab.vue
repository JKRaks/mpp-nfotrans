<script setup lang="ts">
import { inject, onMounted, onUnmounted, ref, shallowRef } from 'vue'
import { TRANSLATION_KEY, labels } from '../useTranslation'
import type { Page } from '../types'
const state = inject(TRANSLATION_KEY)!
const page = shallowRef<Page>(),
  selected = ref<number[]>([]),
  deletion = ref<number[]>([])
const provider = ref(''),
  status = ref(''),
  loading = ref(false)
let disposed = false
function selectPage(select: boolean) {
  selected.value = select ? page.value?.items.map((row) => row.id) || [] : []
  deletion.value = []
}
async function load(number = 1) {
  loading.value = true
  selected.value = []
  deletion.value = []
  try {
    const params = { page: number, page_size: 30, status: status.value, provider: provider.value }
    let value = await state.api.get<Page>(state.url('history'), { params })
    const last = Math.max(1, Math.ceil(value.total / value.page_size))
    if (value.page > last)
      value = await state.api.get<Page>(state.url('history'), { params: { ...params, page: last } })
    if (!disposed) page.value = value
  } finally {
    loading.value = false
  }
}
async function remove() {
  const ids = [...deletion.value]
  if (!ids.length) return
  await state.api.post(state.url('delete'), { ids })
  state.closeDetail()
  deletion.value = []
  selected.value = []
  state.notice = `已删除 ${ids.length} 条调用记录，缓存和巡检待办保留`
  await load(page.value?.page || 1)
}
onMounted(() => {
  void state.run('正在读取调用记录…', () => load())
})
onUnmounted(() => {
  disposed = true
})
</script>
<template>
  <section aria-label="调用记录">
    <fieldset class="history-actions" :disabled="state.busy">
      <form class="row toolbar" @submit.prevent="state.run('正在查询记录…', () => load())">
        <select v-model="provider" aria-label="服务筛选">
          <option value="">全部服务</option>
          <option v-for="(name, id) in state.settings?.providers" :key="id" :value="id">
            {{ name }}
          </option>
        </select>
        <select v-model="status" aria-label="状态筛选">
          <option value="">全部状态</option>
          <option value="complete">候选已完成</option>
          <option value="partial">部分完成</option>
          <option value="failed">失败</option>
          <option value="translated">连接检查成功</option>
        </select>
        <button type="submit">查询</button>
      </form>
      <div class="row selection-bar">
        <span>已选 {{ selected.length }} 条</span
        ><button
          type="button"
          class="text-button"
          :disabled="!page?.items.length"
          @click="selectPage(true)"
        >
          选择本页</button
        ><button
          type="button"
          class="text-button"
          :disabled="!selected.length"
          @click="selectPage(false)"
        >
          取消选择</button
        ><button
          type="button"
          class="danger"
          :disabled="!selected.length"
          @click="deletion = [...selected]"
        >
          删除选中记录
        </button>
      </div>
    </fieldset>
    <p class="hint">记录表示翻译候选或连接检查结果，不代表媒体文件已经写入。</p>
    <p v-if="loading" class="empty" role="status">正在读取调用记录…</p>
    <template v-else-if="page">
      <div v-if="!page.items.length" class="empty">
        <h3>{{ provider || status ? '没有符合筛选条件的记录' : '暂无调用记录' }}</h3>
        <p>
          {{
            provider || status
              ? '调整服务或状态筛选后重新查询。'
              : '检查连接或生成翻译预览后，记录会显示在这里。'
          }}
        </p>
      </div>
      <div v-else class="history-list">
        <div class="history-heading">
          <span></span><span>调用内容</span><span>服务与时间</span><span>状态</span
          ><span>操作</span>
        </div>
        <article v-for="row in page.items" :key="row.id" class="history-row">
          <input
            type="checkbox"
            :value="row.id"
            v-model="selected"
            :disabled="state.busy"
            :aria-label="'选择记录：' + row.summary"
            @change="deletion = []"
          />
          <div class="history-summary">{{ row.summary }}</div>
          <div class="history-meta">
            <span>{{ state.settings?.providers[row.provider] || '来源补齐' }}</span
            ><time class="hint">{{ new Date(row.created * 1000).toLocaleString() }}</time>
          </div>
          <span
            class="badge"
            :class="
              row.status === 'failed' ? 'error' : row.status === 'partial' ? 'warning' : 'success'
            "
            >{{ row.status === 'translated' ? '连接成功' : labels[row.status] || row.status }}</span
          >
          <div class="row history-buttons">
            <button
              class="text-button"
              :disabled="state.busy"
              @click="
                state.showDetail('翻译调用详情', () =>
                  state.api.get(state.url('detail'), { params: { id: row.id } }),
                )
              "
            >
              详情</button
            ><button class="text-button danger" :disabled="state.busy" @click="deletion = [row.id]">
              删除
            </button>
          </div>
        </article>
      </div>
      <div
        v-if="deletion.length"
        class="confirm-panel"
        role="alertdialog"
        aria-label="删除调用记录"
      >
        <p>
          删除{{ deletion.length === 1 ? '这条' : '选中的 ' + deletion.length + ' 条' }}调用记录？
        </p>
        <p class="hint">仅删除记录，保留缓存、媒体备份和 NfoCheck 巡检待办。</p>
        <div class="row end">
          <button :disabled="state.busy" @click="deletion = []">取消</button
          ><button
            class="danger"
            :disabled="state.busy"
            @click="state.run('正在删除记录…', remove)"
          >
            确认删除
          </button>
        </div>
      </div>
      <div class="row between pagination">
        <span class="hint"
          >第 {{ page.page }} / {{ Math.max(1, Math.ceil(page.total / page.page_size)) }} 页 · 共
          {{ page.total }} 条</span
        >
        <div class="row">
          <button
            :disabled="state.busy || page.page <= 1"
            @click="state.run('正在读取记录…', () => load(page!.page - 1))"
          >
            上一页</button
          ><button
            :disabled="state.busy || page.page * page.page_size >= page.total"
            @click="state.run('正在读取记录…', () => load(page!.page + 1))"
          >
            下一页
          </button>
        </div>
      </div>
    </template>
  </section>
</template>
