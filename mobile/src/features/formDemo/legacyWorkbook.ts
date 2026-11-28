import * as CFB from 'cfb'
import {detectField,reservedLabel,startsProtectedSection} from './formFields'

const invalid = () => Error('此 XLS 结构暂不支持可靠写回，请在 Excel 或 WPS 核对原件。')
const u16 = (a:Uint8Array,p:number)=>new DataView(a.buffer,a.byteOffset,a.byteLength).getUint16(p,true)
const u32 = (a:Uint8Array,p:number)=>new DataView(a.buffer,a.byteOffset,a.byteLength).getUint32(p,true)
const set32 = (a:Uint8Array,p:number,n:number)=>new DataView(a.buffer,a.byteOffset,a.byteLength).setUint32(p,n,true)
const set16 = (a:Uint8Array,p:number,n:number)=>new DataView(a.buffer,a.byteOffset,a.byteLength).setUint16(p,n,true)
function join(parts:Uint8Array[]) {
  const out=new Uint8Array(parts.reduce((n,p)=>n+p.length,0))
  let offset=0
  for (const part of parts) { out.set(part,offset); offset+=part.length }
  return out
}
type RecordInfo={offset:number;type:number;body:Uint8Array}
function records(data:Uint8Array,offset:number) {
  const out:RecordInfo[]=[]
  while (offset+4<=data.length && out.length<150000) {
    const type=u16(data,offset), end=offset+4+u16(data,offset+2)
    if (end>data.length || end-offset>8228) throw invalid()
    out.push({offset,type,body:data.subarray(offset+4,end)})
    if (type===0x0a) return out
    offset=end
  }
  throw invalid()
}
function chars(bytes:Uint8Array,at:number,n:number,wide:boolean) {
  if (at+n*(wide?2:1)>bytes.length) throw invalid()
  return Array.from({length:n},(_,i)=>String.fromCharCode(wide?u16(bytes,at+i*2):bytes[at+i])).join('')
}
function strings(body:Uint8Array) {
  const list:string[]=[]
  let p=8
  const count=u32(body,4)
  if (count>50000) throw invalid()
  for(let i=0;i<count;i++){
    const n=u16(body,p), flags=body[p+2]; p+=3
    let extra=0
    if (flags&8) {extra+=4*u16(body,p);p+=2}
    if (flags&4) {extra+=u32(body,p);p+=4}
    list.push(chars(body,p,n,Boolean(flags&1)))
    p+=n*((flags&1)?2:1)+extra
    if(p>body.length) throw invalid()
  }
  return list
}
function address(row:number,col:number) {
  let letters=''
  for(let v=col+1;v;v=Math.floor((v-1)/26)) letters=String.fromCharCode(65+(v-1)%26)+letters
  return letters+(row+1)
}
export type XlsField={id:string;label:string;sheet:string;cell:string}
type Target={row:number;col:number;offset:number;xf:number}
export function inspectLegacyWorkbook(bytes:Uint8Array) {
  if(bytes.length>10*1024*1024 || bytes.slice(0,8).join(',')!=='208,207,17,224,161,177,26,225') throw invalid()
  const cfb=CFB.read(bytes,{type:'array'})
  if(cfb.FullPaths.some(p=>/\/(?:VBA|_VBA_PROJECT_CUR|ObjectPool|DigitalSignature)(?:\/|$)/i.test(p))) throw invalid()
  const entry=CFB.find(cfb,'/Workbook')
  if(!entry) throw invalid()
  const entryName=entry.name
  const stream=Uint8Array.from(entry.content)
  const globals=records(stream,0)
  if(globals[0].type!==0x809 || u16(globals[0].body,0)!==0x600 || globals.some(r=>r.type===0x2f)) throw invalid()
  const sst=globals.find(r=>r.type===0xfc)
  const names=sst?strings(sst.body):[]
  const bounds=globals.filter(r=>r.type===0x85)
  const pointers:RecordInfo[]=[...bounds], fields:XlsField[]=[], targets=new Map<string,Target>()
  const blankRecords=new Map<number,RecordInfo>()
  for(const b of bounds){
    if (b.body[5]!==0) throw invalid()
    const sheet=chars(b.body,8,b.body[6],Boolean(b.body[7]&1))
    const recs=records(stream,u32(b.body,0))
    pointers.push(...recs.filter(r=>r.type===0x20b || r.type===0xd7))
    if(b.body[4]!==0 || recs.some(r=>r.type===0x12 && u16(r.body,0)!==0)) continue
    const cells=new Map<string,Target>(), labels:{row:number;col:number;text:string}[]=[]
    const merges:{firstRow:number;lastRow:number;firstCol:number;lastCol:number}[]=[]
    for(const r of recs){
      const d=r.body
      if(r.type===0xe5){
        for(let i=0;i<u16(d,0);i++){const p=2+8*i;merges.push({firstRow:u16(d,p),lastRow:u16(d,p+2),firstCol:u16(d,p+4),lastCol:u16(d,p+6)})}
      }else if(r.type===0xfd || r.type===0x204){
        const text=r.type===0xfd?names[u32(d,6)]:chars(d,9,u16(d,6),Boolean(d[8]&1))
        if(text)labels.push({row:u16(d,0),col:u16(d,2),text})
      }else if(r.type===0x201 || r.type===0xbe){
        const row=u16(d,0),first=u16(d,2),last=r.type===0xbe?u16(d,d.length-2):first
        if(last>255 || first>last || (r.type===0xbe && d.length!==6+2*(last-first+1)))throw invalid()
        blankRecords.set(r.offset,r)
        for(let col=first;col<=last;col++)cells.set(address(row,col),{row,col,xf:u16(d,4+2*(col-first)),offset:r.offset})
      }
    }
    const protectedRows=new Set(labels.filter(l=>reservedLabel(l.text)).map(l=>l.row))
    const sectionStart=Math.min(...labels.filter(l=>startsProtectedSection(l.text)).map(l=>l.row),Infinity)
    for(const {row,col,text} of labels){
      if(row>=sectionStart || protectedRows.has(row) || !detectField(text))continue
      const labelMerge=merges.find(m=>m.firstRow===row && m.firstCol===col)
      const next=(labelMerge?.lastCol??col)+1, cell=address(row,next),target=cells.get(cell)
      const merged=merges.find(m=>m.firstRow<=row && row<=m.lastRow && m.firstCol<=next && next<=m.lastCol)
      if(!target || (merged && (merged.firstRow!==row || merged.firstCol!==next)))continue
      const id=JSON.stringify([sheet,cell])
      targets.set(id,target);fields.push({id,label:text,sheet,cell})
    }
  }
  function exportCopy(values:Record<string,string>){
    const edits=new Map<number,Map<number,string>>()
    for(const [id,value] of Object.entries(values)){
      if(!value)continue
      const t=targets.get(id)
      if(!t || value.length>1000)throw invalid()
      const group=edits.get(t.offset)??new Map<number,string>()
      group.set(t.col,value);edits.set(t.offset,group)
    }
    if(!edits.size)throw Error('请先填写申请人字段。')
    const chunks:Uint8Array[]=[],shifts:{end:number;delta:number}[]=[]
    let cursor=0,delta=0
    for(const [off,group] of [...edits].sort(([a],[b])=>a-b)){
      const r=blankRecords.get(off)!,d=r.body,row=u16(d,0),first=u16(d,2)
      const last=r.type===0xbe?u16(d,d.length-2):first
      chunks.push(stream.subarray(cursor,off))
      let length=0
      for(let col=first;col<=last;col++){
        const value=group.get(col),part=new Uint8Array(value?13+2*value.length:10)
        set16(part,0,value?0x204:0x201);set16(part,2,part.length-4)
        set16(part,4,row);set16(part,6,col);set16(part,8,u16(d,4+2*(col-first)))
        if(value){set16(part,10,value.length);part[12]=1;for(let i=0;i<value.length;i++)set16(part,13+i*2,value.charCodeAt(i))}
        chunks.push(part);length+=part.length
      }
      cursor=off+4+d.length;delta+=length-4-d.length;shifts.push({end:cursor,delta})
    }
    chunks.push(stream.subarray(cursor))
    const result=join(chunks)
    const moved=(n:number)=>{
      let lo=0,hi=shifts.length
      while(lo<hi){
        const mid=Math.floor((lo+hi)/2)
        if(shifts[mid].end<=n)lo=mid+1
        else hi=mid
      }
      return n+(lo?shifts[lo-1].delta:0)
    }
    for(const r of pointers){
      const p=moved(r.offset)+4,d=r.body
      if(r.type===0x85)set32(result,p,moved(u32(d,0)))
      if(r.type===0x20b)for(let i=12;i+4<=d.length;i+=4)set32(result,p+i,moved(u32(d,i)))
      if(r.type===0xd7){
        const first=r.offset-u32(d,0)
        set32(result,p,moved(r.offset)-moved(first))
        let prev=first+4+u16(stream,first+2)
        for(let i=4;i+2<=d.length;i+=2){
          const next=prev+u16(d,i),distance=moved(next)-moved(prev)
          if(distance>65535)throw invalid()
          set16(result,p+i,distance);prev=next
        }
      }
    }
    CFB.utils.cfb_add(cfb,entryName,result)
    const out=Uint8Array.from(CFB.write(cfb,{type:'array',fileType:'cfb'}))
    return new Blob([out],{type:'application/vnd.ms-excel'})
  }
  return {fields,exportCopy}
}
