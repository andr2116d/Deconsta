<script setup lang="ts">
// Ilustración de fondo: un recibo por pagar y una constancia de pago. No contiene datos reales.
defineProps<{ variante: 'recibo' | 'constancia' }>()
</script>

<template>
  <article
    aria-hidden="true"
    class="w-[230px] rounded-[3px] bg-white px-6 py-6 text-[10px] text-secundario shadow-[0_9px_30px_#30233012]"
  >
    <div class="flex items-center gap-2 text-[12px] font-extrabold text-ciruela">
      <svg viewBox="0 0 24 24" class="size-4 fill-none stroke-current stroke-2">
        <path
          v-if="variante === 'recibo'"
          d="M12 3v2m0 14v2M3 12h2m14 0h2M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8Z"
        />
        <path v-else d="m5 12 4.5 4.5L19 7" />
      </svg>
      {{ variante === 'recibo' ? 'Servicio de luz' : 'Constancia de pago' }}
    </div>
    <hr class="my-4 border-t border-dashed border-borde" />
    <p>{{ variante === 'recibo' ? 'Obligación de pago' : 'Pago de servicio' }}</p>
    <p class="mt-2 mb-0.5 text-[16px] font-bold tracking-[-0.03em] text-tinta">
      {{ variante === 'recibo' ? 'Recibo mensual' : 'Operación realizada' }}
    </p>
    <span
      v-if="variante === 'constancia'"
      class="mt-2 inline-block rotate-12 rounded-[5px] border border-exito px-2 py-1 text-[9px] text-exito"
    >
      Verificado
    </span>
    <hr class="my-4 border-t border-dashed border-borde" />
    <p>{{ variante === 'recibo' ? 'Total a pagar' : 'Importe pagado' }}</p>
    <p class="my-2 text-[27px] font-extrabold text-tinta">
      {{ variante === 'recibo' ? 'S/ 482.50' : 'S/ 325.00' }}
    </p>
    <div class="mt-5 flex h-6 justify-center gap-[2px]">
      <i
        v-for="n in 34"
        :key="n"
        class="block h-full bg-tinta"
        :style="{ width: `${(n * 7) % 3 === 0 ? 3 : 1}px` }"
      />
    </div>
    <p class="mt-3 text-center text-[9px]">Documento ilustrativo · Deconsta</p>
  </article>
</template>
