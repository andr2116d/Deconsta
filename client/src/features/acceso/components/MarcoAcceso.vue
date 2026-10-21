<script setup lang="ts">
import MarcaDeconsta from '@/shared/components/MarcaDeconsta.vue'

import ReciboDecorativo from './ReciboDecorativo.vue'

const anio = new Date().getFullYear()
</script>

<template>
  <div
    data-fondo="acceso"
    class="relative flex min-h-dvh flex-col items-center overflow-hidden bg-acceso px-4 py-6 sm:px-10 sm:py-8"
  >
    <header class="relative z-10 flex w-full items-center justify-between gap-4">
      <MarcaDeconsta />
      <span class="text-right text-[12px] text-secundario">Todo pago, con constancia.</span>
    </header>

    <div aria-hidden="true" class="relative z-0 mt-6 select-none sm:mt-9">
      <MarcaDeconsta tamano="gigante" />
    </div>

    <main class="relative z-10 flex w-full max-w-[1000px] justify-center pt-4 pb-9 sm:pt-5">
      <ReciboDecorativo
        variante="recibo"
        class="absolute top-12 left-0 hidden -rotate-12 opacity-80 motion-safe:animate-flotar lg:block xl:left-7"
      />
      <ReciboDecorativo
        variante="constancia"
        class="absolute top-24 right-0 hidden rotate-12 opacity-80 motion-safe:animate-flotar motion-safe:[animation-delay:-3s] lg:block xl:right-4"
      />
      <section
        class="relative z-10 w-full max-w-[410px] animate-aparecer rounded-2xl bg-white p-6 shadow-[0_18px_65px_#64294918] sm:p-8"
      >
        <slot />
      </section>
    </main>

    <footer
      class="relative z-10 mt-auto flex flex-wrap justify-center gap-x-6 gap-y-1 text-[12px] text-secundario"
    >
      <span>© Deconsta {{ anio }}</span>
      <span>Tu rol viaja con tu cuenta.</span>
    </footer>
  </div>
</template>
