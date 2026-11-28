import {PDFDocument,PDFName,PDFDict,PDFSignature,PDFTextField,concatTransformationMatrix,drawObject,
  popGraphicsState,pushGraphicsState,degrees} from 'pdf-lib'
import {reservedLabel} from './formFields'

export type PdfMark={page:number;x:number;y:number;angle:number;text:string;size:number}
export async function inspectPdfOriginal(bytes:Uint8Array,name:string){
  if(bytes.length>10*1024*1024)throw Error('文件超过 10 MB。')
  let doc:PDFDocument
  if(/\.(jpg|jpeg|png)$/i.test(name)){
    if (/\.png$/i.test(name)) {
      if(bytes.length<24)throw Error('扫描图片头不完整。')
      const view=new DataView(bytes.buffer,bytes.byteOffset,bytes.byteLength)
      const width=view.getUint32(16),height=view.getUint32(20)
      if(!width || !height || width*height>32000000)throw Error('扫描图片尺寸无效或过大。')
    }
    doc=await PDFDocument.create()
    const image=/\.png$/i.test(name)?await doc.embedPng(bytes):await doc.embedJpg(bytes)
    if(image.width*image.height>32000000)throw Error('扫描图片过大，请缩小后重试。')
    const scale=Math.min(1,842/Math.max(image.width,image.height))
    const page=doc.addPage([image.width*scale,image.height*scale])
    page.drawImage(image,{width:page.getWidth(),height:page.getHeight()})
    bytes=Uint8Array.from(await doc.save())
  }else{
    doc=await PDFDocument.load(bytes,{updateMetadata:false})
  }
  const acro=doc.catalog.lookupMaybe(PDFName.of('AcroForm'),PDFDict)
  if(doc.isEncrypted || doc.catalog.has(PDFName.of('Perms')) || acro?.has(PDFName.of('XFA')) ||
     doc.getPageCount()>150)throw Error('此 PDF 有保护、动态表单或超过页数限制，请在原件中处理。')
  const form=acro?doc.getForm():undefined
  const fields=form?.getFields()??[]
  if(fields.some(f=>f instanceof PDFSignature && f.acroField.dict.has(PDFName.of('V'))))
    throw Error('原件已有签名，请保留签署版本。')
  const editable=fields.filter((f):f is PDFTextField=>f instanceof PDFTextField && !f.isReadOnly() &&
    !f.getText() && !f.isPassword() && !f.isFileSelector() && !f.isCombed() && f.acroField.getWidgets().length===1 &&
    !reservedLabel(f.getName()) && !/signature|reviewer|advisor|instructor|teacher|approval|official|registrar|supervisor/i.test(f.getName()))
    .map(f=>{
      const widget=f.acroField.getWidgets()[0]
      const page=doc.getPages().find(p=>p.ref===widget.P() || p.node.Annots()?.asArray().some(r=>doc.context.lookup(r)===widget.dict))
      return {name:f.getName(),page:page?doc.getPages().indexOf(page):-1,max:f.getMaxLength()??500}
    }).filter(f=>f.page>=0)
  return {bytes,editable,interactive:fields.length>0}
}
function stamp(text:string,size:number,maxWidth?:number){
  const canvas=document.createElement('canvas')
  const ctx=canvas.getContext('2d')!
  const fontSize=48
  ctx.font=fontSize+'px sans-serif'
  const w=Math.ceil(ctx.measureText(text).width)+4
  if(w>16000 || !text.trim() || /[\r\n]/.test(text))throw Error('请分行填写，单行文字过长。')
  canvas.width=w;canvas.height=64
  ctx.font=fontSize+'px sans-serif';ctx.fillStyle='#151515';ctx.fillText(text,2,49)
  const scale=Math.min(size/fontSize,maxWidth?maxWidth/w:Infinity)
  return {png:canvas.toDataURL('image/png'),width:w*scale,height:64*scale}
}
export async function writePdfOriginal(original:Awaited<ReturnType<typeof inspectPdfOriginal>>,
                                      values:Record<string,string>,marks:PdfMark[]){
  const doc=await PDFDocument.load(original.bytes,{updateMetadata:false})
  if(original.interactive && marks.length)throw Error('交互式 PDF 仅可写入已核对的申请人文本框。')
  for(const [key,text] of Object.entries(values)){
    if(!text)continue
    const spec=original.editable.find(f=>f.name===key)
    if(!spec || text.length>Math.min(spec.max,500))throw Error('PDF 文本框位置或长度待核对。')
    const form=doc.getForm(),field=form.getTextField(key),widget=field.acroField.getWidgets()[0]
    const {width,height}=widget.getRectangle()
    field.setText(text)
    const bitmap=stamp(text,Math.min(12,height*0.65),width-2)
    const image=await doc.embedPng(bitmap.png)
    const appearance=doc.context.formXObject([pushGraphicsState(),
      concatTransformationMatrix(bitmap.width,0,0,bitmap.height,1,(height-bitmap.height)/2),
      drawObject('TextImage'),popGraphicsState()],{BBox:[0,0,width,height],Resources:{XObject:{TextImage:image.ref}}})
    widget.setNormalAppearance(doc.context.register(appearance))
    form.markFieldAsClean(field.ref)
  }
  for(const mark of marks){
    const page=doc.getPage(mark.page),bitmap=stamp(mark.text,mark.size)
    const image=await doc.embedPng(bitmap.png)
    page.drawImage(image,{x:mark.x,y:mark.y,width:bitmap.width,height:bitmap.height,rotate:degrees(mark.angle)})
  }
  const result=Uint8Array.from(await doc.save({updateFieldAppearances:false}))
  return new Blob([result],{type:'application/pdf'})
}
