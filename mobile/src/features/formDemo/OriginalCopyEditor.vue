<script setup lang="ts">
import {computed,nextTick,onBeforeUnmount,onMounted,ref,shallowRef,watch} from 'vue'
import {getDocument,GlobalWorkerOptions,type PDFDocumentProxy,type PageViewport} from 'pdfjs-dist/legacy/build/pdf.mjs'
import workerUrl from 'pdfjs-dist/legacy/build/pdf.worker.min.mjs?url'
import {inspectLegacyWorkbook} from './legacyWorkbook'
import {inspectPdfOriginal,writePdfOriginal,type PdfMark} from './pdfOriginal'

GlobalWorkerOptions.workerSrc=workerUrl
const props=defineProps<{file:File;verify?:()=>Promise<void>}>()
const error=ref(''),busy=ref(true),confirmed=ref(false),page=ref(1),size=ref(12),input=ref('')
const canvas=ref<HTMLCanvasElement>(),viewport=shallowRef<PageViewport>()
const sheet=shallowRef<ReturnType<typeof inspectLegacyWorkbook>>()
const pdf=shallowRef<Awaited<ReturnType<typeof inspectPdfOriginal>>>()
const viewer=shallowRef<PDFDocumentProxy>()
const values=ref<Record<string,string>>(Object.create(null))
const marks=ref<(PdfMark & {left:number;top:number})[]>([])
const stem=ref(props.file.name.replace(/\.[^.]+$/,'')+'-填写')
let loadingTask:ReturnType<typeof getDocument>|undefined
let alive=true
let rendering:ReturnType<Awaited<ReturnType<PDFDocumentProxy['getPage']>>['render']>|undefined
let renderVersion=0
const ocrText=ref('')
watch(page,()=>{ocrText.value=''})
async function recognizePage(){
  if(!canvas.value || !viewport.value || busy.value)return
  busy.value=true;error.value='';ocrText.value=''
  try{
    const {readScan}=await import('./scanRecognition')
    const text=await readScan(canvas.value)
    if(alive)ocrText.value=text.trim() || '未识别到文字，请对照原页填写。'
  }catch{if(alive)error.value='本机识别失败，可以继续对照原页定位。'}
  finally{busy.value=false}
}
const edited=computed(()=>Object.values(values.value).some(Boolean)||marks.value.length>0)
watch([values,marks,stem],()=>{confirmed.value=false},{deep:true,flush:'sync'})
async function render(){
  const version=++renderVersion
  rendering?.cancel()
  viewport.value=undefined
  if(!viewer.value || !canvas.value)return
  try{
    const p=await viewer.value.getPage(page.value)
    if(version!==renderVersion || !alive)return
    const native=p.getViewport({scale:1})
    const view=p.getViewport({scale:Math.min(2,1400/Math.max(native.width,native.height))})
    canvas.value.width=Math.ceil(view.width);canvas.value.height=Math.ceil(view.height)
    rendering=p.render({canvas:canvas.value,viewport:view})
    await rendering.promise
    if(alive && version===renderVersion)viewport.value=view
  }catch(e){if(alive && version===renderVersion)error.value='此页无法渲染，请在原件中核对。'}
}
watch(page,render)
onMounted(async()=>{
  try{
    if(props.file.size>10*1024*1024)throw Error('附件超过 10 MB。')
    const bytes=new Uint8Array(await props.file.arrayBuffer())
    if(/\.xls$/i.test(props.file.name))sheet.value=inspectLegacyWorkbook(bytes)
    else{
      const original=await inspectPdfOriginal(bytes,props.file.name)
      if(!alive)return
      loadingTask=getDocument({data:original.bytes.slice(),useSystemFonts:true})
      const doc=await loadingTask.promise
      if(!alive)return
      pdf.value=original;viewer.value=doc;await nextTick();await render()
    }
  }catch(e){error.value=e instanceof Error?e.message:'原件暂不能核验。'}
  finally{busy.value=false}
})
onBeforeUnmount(()=>{alive=false;renderVersion++;rendering?.cancel();void loadingTask?.destroy()})
function place(event:MouseEvent){
  const view=viewport.value
  if(!view || !canvas.value || pdf.value?.interactive || !input.value.trim())return
  const rect=canvas.value.getBoundingClientRect()
  const left=(event.clientX-rect.left)/rect.width,top=(event.clientY-rect.top)/rect.height
  const [x,y]=view.convertToPdfPoint(left*view.width,top*view.height)
  const [right,up]=view.convertToPdfPoint(left*view.width+1,top*view.height)
  const measure=document.createElement('canvas').getContext('2d')!
  measure.font='48px sans-serif'
  if((measure.measureText(input.value).width+4)*size.value/48*view.scale>(1-left)*view.width ||
     size.value*64/48*view.scale>top*view.height){error.value='文字超出页边，请调整位置或字号。';return}
  marks.value.push({x,y,left,top,page:page.value-1,angle:Math.atan2(up-y,right-x)*180/Math.PI,text:input.value,size:size.value})
  input.value='';error.value=''
}
async function download(){
  if(!confirmed.value || busy.value || !edited.value)return
  busy.value=true;error.value=''
  try{
    if(!stem.value.trim() || /[<>:"/\\|?*\u0000-\u001f]/.test(stem.value))throw Error('请核对文件名。')
    const result=sheet.value?sheet.value.exportCopy(values.value):await writePdfOriginal(pdf.value!,values.value,marks.value)
    if(!alive)return
    await props.verify?.()
    if(!alive)return
    const url=URL.createObjectURL(result),a=document.createElement('a')
    a.href=url;a.download=stem.value.trim()+(sheet.value?'.xls':'.pdf');a.click()
    setTimeout(()=>URL.revokeObjectURL(url),30000)
  }catch(e){confirmed.value=false;error.value=e instanceof Error?e.message:'生成失败，请重新核对。'}
  finally{busy.value=false}
}
</script>
<template>
  <fieldset :disabled="busy" aria-label="填写原件副本">
    <legend>{{ file.name }}</legend>
    <p v-if="busy" role="status">正在核对原件…</p>
    <p v-if="error" role="alert">{{ error }}</p>
    <template v-if="sheet">
      <p v-if="!sheet.fields.length">没有可核对的申请人空格，请在 Excel 或 WPS 中处理。</p>
      <label v-for="field in sheet.fields" :key="field.id">{{ field.label }} · {{ field.sheet }} {{ field.cell }}
        <input v-model="values[field.id]" maxlength="1000">
      </label>
    </template>
    <template v-if="pdf && viewer">
      <label>原件页码 <select v-model="page"><option v-for="n in viewer.numPages" :value="n" :key="n">{{ n }}</option></select></label>
      <div v-if="!pdf.interactive">
        <button type="button" :disabled="!viewport" @click="recognizePage">本机识别本页文字</button>
        <details v-if="ocrText" open><summary>第 {{ page }} 页识别结果 · 待核对</summary><pre>{{ ocrText }}</pre></details>
        <label>申请人填写内容 <input v-model="input" maxlength="250"></label>
        <label>字号 <select v-model="size"><option v-for="n in [8,10,12,14,16,18]" :key="n" :value="n">{{ n }}</option></select></label>
        <p>输入一行文字，再点选原页上的申请人空白位置。签名、盖章和审核区请留给对应人员。</p>
      </div>
      <div class="sheet-preview" @click="place"><canvas ref="canvas" aria-label="原件页面预览"></canvas>
        <span v-for="(m,i) in marks" v-show="m.page===page-1" :key="i"
          :style="{left:m.left*100+'%',top:m.top*100+'%',fontSize:viewport ? (m.size*viewport.scale/viewport.width*100)+'cqw':undefined}">{{ m.text }}</span>
      </div>
      <button v-if="marks.length" type="button" @click="marks.pop()">撤回最后一处文字</button>
      <label v-for="field in pdf.editable.filter(f=>f.page===page-1)" :key="field.name">
        第 {{ page }} 页 · {{ field.name }} <input :aria-label="field.name" v-model="values[field.name]" :maxlength="Math.min(field.max,500)">
      </label>
      <p v-if="pdf.interactive && !pdf.editable.some(f=>f.page===page-1)">此页无可填写的空白申请人文本框。</p>
    </template>
    <template v-if="edited">
      <label>副本文件名 <input v-model="stem" maxlength="120"></label>
      <label><input v-model="confirmed" type="checkbox">我已核对通知、申请人位置、填写内容和文件名</label>
      <button type="button" :disabled="!confirmed" @click="download">下载填写副本</button>
    </template>
  </fieldset>
</template>
<style scoped>
label{display:block;margin:.6rem 0}.sheet-preview{position:relative;container-type:inline-size;max-width:800px}
canvas{width:100%;height:auto;display:block}.sheet-preview span{position:absolute;transform:translateY(-100%);pointer-events:none;white-space:pre}
</style>
