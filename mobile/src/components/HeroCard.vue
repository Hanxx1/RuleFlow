<script setup lang="ts">
defineProps<{title:string;description:string;image:string}>();
</script>

<template>
  <section class="hero-card">
    <div class="hero-card__content"><h2>{{title}}</h2><p>{{description}}</p><slot/></div>
    <img class="hero-card__image" :src="image" alt="" aria-hidden="true">
  </section>
</template>
