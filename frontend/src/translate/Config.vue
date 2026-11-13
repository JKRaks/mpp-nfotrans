<script setup lang="ts">
import App from './App.vue'
import type {HostProps} from '../types'
defineProps<HostProps>()
const emit = defineEmits(['close'])
</script>
<template><App :api="api" :plugin-id="pluginId" @close="emit('close')" /></template>
