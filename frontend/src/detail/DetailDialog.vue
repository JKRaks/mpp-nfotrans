<script setup lang="ts">
import {onMounted, onUnmounted, ref} from 'vue'
import PluginClose from '../PluginClose.vue'
import DetailReadout from './DetailReadout.vue'
import type {DetailSession} from './useDetail'

withDefaults(defineProps<{session: DetailSession; modelValue?: boolean}>(), {modelValue: true})
const emit = defineEmits<{(event: 'close'): void}>()
const media = window.matchMedia('(max-width: 700px)')
const mobile = ref(media.matches)
const titleElement = ref<HTMLElement>()
const bodyElement = ref<HTMLElement>()
function resize() { mobile.value = media.matches }
onMounted(() => media.addEventListener('change', resize))
onUnmounted(() => media.removeEventListener('change', resize))

</script>
<template>
  <v-dialog
    :model-value="modelValue" :fullscreen="mobile" :width="mobile ? undefined : 920"
    :aria-label="session.title"
    @update:model-value="(visible: boolean) => { if (!visible) emit('close') }"
    @after-enter="titleElement?.focus({preventScroll:true})"
  >
    <article class="detail-frame" @keydown.esc.stop.prevent="emit('close')">
      <header class="detail-heading">
        <div>
          <h2 ref="titleElement" tabindex="-1">{{session.title}}</h2>
          <p v-if="session.subtitle" class="subtitle">{{session.subtitle}}</p>
        </div>
        <PluginClose @close="emit('close')"/>
      </header>
      <div ref="bodyElement" class="detail-body" :aria-busy="!!session.loading">
        <p v-if="session.loading" class="status" role="status">正在读取详情…</p>
        <p v-else-if="session.error" class="status error" role="alert">{{session.error}}</p>
        <DetailReadout v-else :data="session.data" @navigate="bodyElement?.scrollTo({top: 0})"/>
      </div>
    </article>
  </v-dialog>
</template>
<style scoped>
.detail-frame {
  --line: rgba(var(--v-theme-on-surface, 43, 48, 58), .17);
  --muted: rgba(var(--v-theme-on-surface, 43, 48, 58), .68);
  --tint: rgba(var(--v-theme-on-surface, 43, 48, 58), .05);
  --accent: rgb(var(--v-theme-primary, 82, 105, 205));
  display: flex; flex-direction: column; width: 100%; min-height: 0;
  max-height: min(88dvh, 900px); overflow: hidden; border-radius: 12px;
  color: rgb(var(--v-theme-on-surface, 43, 48, 58)); background: rgb(var(--v-theme-surface, 255, 255, 255));
  font: inherit; font-size: 15px; text-align: start;
}
.detail-heading {display: flex; flex: none; align-items: center; justify-content: space-between; gap: 12px; padding: 14px 20px; border-bottom: 1px solid var(--line)}
.detail-heading > div {min-width: 0}
.detail-heading h2 {font-size: 19px; font-weight: 600; line-height: 1.4; margin: 0; overflow-wrap: anywhere}
.detail-heading h2:focus {outline: none}
.subtitle {margin: 2px 0 0; font-size: 13px; color: var(--muted); overflow-wrap: anywhere}
.detail-body {min-height: 0; overflow: auto; overscroll-behavior: contain}
.status {padding: 20px; margin: 0; overflow-wrap: anywhere}
.error {color: rgb(var(--v-theme-error, 169, 41, 49))}
@media(max-width: 700px) {
  .detail-frame {height: 100dvh; max-height: 100%; border-radius: 0}
  .detail-heading {padding: max(10px, env(safe-area-inset-top)) 12px 10px}
  .detail-body {flex: 1; padding-bottom: env(safe-area-inset-bottom)}
  .subtitle {display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden}
}
</style>
