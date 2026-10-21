<script setup lang="ts">
import { RouterView } from 'vue-router'
</script>

<template>
  <RouterView v-slot="{ Component }">
    <Transition name="vista" mode="out-in">
      <component :is="Component" />
    </Transition>
  </RouterView>
</template>
