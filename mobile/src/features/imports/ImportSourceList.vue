<script setup lang="ts">
import type {ImportSourceListItem} from '../../types/product';
withDefaults(defineProps<{sources:ImportSourceListItem[];removable?:boolean}>(),{removable:true});
defineEmits<{remove:[id:string]}>();
function icon(kind:string){return kind==='url'?'/assets/icons/files/file_link.svg':kind==='file'?'/assets/icons/actions/icon_attach.svg':'/assets/icons/status/icon_info.svg'}
</script>

<template>
  <div class="import-source-list"><article v-for="item in sources" :key="item.id" :class="['import-source-row',{'import-source-row--failed':item.status==='failed'}]"><span class="import-source-row__icon"><img :src="icon(item.kind)" alt=""></span><span><strong>{{item.label}}</strong><small>{{item.detail}}</small><small v-if="item.status" class="import-source-row__status">{{item.status==='failed'?'处理失败':item.status==='completed'?'已建立证据':'已保存'}}</small><small v-if="item.error" class="text-danger">{{item.error}}</small></span><button v-if="removable&&item.removable!==false" type="button" :aria-label="`移除${item.label}`" @click="$emit('remove',item.id)"><img src="/assets/icons/actions/icon_delete.svg" alt=""></button></article></div>
</template>
