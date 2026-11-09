import {describe,it,expect} from 'vitest';
import {addDays,weekStart,dayKey,layoutDays,type GridItem} from './scheduleGrid';
const item=(id:string,start:string,end:string):GridItem=>({id,title:id,kind:'task',starts_at:start,ends_at:end,evidence_ids:[]});
const at=(t:string)=>`2026-11-09T${t}:00+08:00`;
const day='2026-11-09';
describe('fixture grid temporal geometry',()=>{
 it('navigates month/year and Monday weeks',()=>{expect(addDays('2026-12-31',1)).toBe('2027-01-01');expect(addDays('2026-03-01',-1)).toBe('2026-02-28');expect(weekStart('2026-11-15')).toBe(day)});
 it('uses Shanghai dates regardless of explicit offset',()=>{expect(dayKey('2026-11-08T16:30:00Z')).toBe(day)});
 it('positions minutes without enlarging short durations',()=>{const r=layoutDays([item('a',at('09:00'),at('10:00')),item('b',at('12:05'),at('12:15'))],[day]);expect(r.days[0].segments.map(x=>[x.start,x.end])).toEqual([[540,600],[725,735]])});
 it('clips midnight without next-day zero fragments',()=>{const r=layoutDays([item('a',at('23:00'),'2026-11-10T00:00:00+08:00')],[day,'2026-11-10']);expect(r.days.map(d=>d.segments.length)).toEqual([1,0]);expect(r.days[0].segments[0].end).toBe(1440)});
 it('splits cross-week and preserves original identity',()=>{const r=layoutDays([item('a','2026-11-15T23:30:00+08:00','2026-11-16T00:30:00+08:00')],['2026-11-15','2026-11-16']);expect(r.days.map(d=>d.segments.map(x=>[x.item.id,x.start,x.end]))).toEqual([[['a',1410,1440]],[['a',0,30]]])});
 it('clips an event spanning the complete visible day',()=>{const r=layoutDays([item('a','2026-11-08T12:00:00Z','2026-11-11T12:00:00Z')],[day]);expect(r.days[0].segments.map(x=>[x.start,x.end])).toEqual([[0,1440]])});
 it('allocates triple/nested overlaps and releases adjacent lanes',()=>{const r=layoutDays([item('a',at('09:00'),at('10:00')),item('b',at('09:30'),at('10:30')),item('c',at('09:45'),at('10:15')),item('d',at('10:30'),at('11:00'))],[day]).days[0];expect(r.segments.map(x=>[x.lane,x.lanes,x.conflict])).toEqual([[0,3,true],[1,3,true],[2,3,true],[0,1,false]]);expect(r.minWidth).toBeGreaterThanOrEqual(144)});
 it('keeps chain overlaps stable when input order changes',()=>{const a=[item('a',at('09:00'),at('10:00')),item('b',at('09:30'),at('10:30')),item('c',at('10:00'),at('11:00'))];const summarize=(v:GridItem[])=>layoutDays(v,[day]).days[0].segments.map(x=>[x.item.id,x.lane,x.lanes]);expect(summarize(a)).toEqual([['a',0,2],['b',1,2],['c',0,2]]);expect(summarize([...a].reverse())).toEqual(summarize(a))});
 it('keeps different IDs at identical times',()=>{expect(layoutDays([item('a',at('09:00'),at('10:00')),item('b',at('09:00'),at('10:00'))],[day]).days[0].segments).toHaveLength(2)});
 it.each([['bad',at('10:00')],[at('10:00'),at('10:00')],[at('11:00'),at('10:00')],['2026-11-09T09:00:00',at('10:00')],['2026-02-30T09:00:00+08:00',at('10:00')]])('rejects invalid interval %s', (a,b)=>{const r=layoutDays([item('invalid',a,b)],[day]);expect(r.errors).toHaveLength(1);expect(r.days[0].segments).toHaveLength(0)});
 it('renders empty days without synthesizing events',()=>{expect(layoutDays([],[day]).days[0].segments).toEqual([])});
});
