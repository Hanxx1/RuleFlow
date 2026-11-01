import {describe,it,expect} from 'vitest';
import {syntheticCourses,expandCourses,parseTimetableText,validateCourse,localSchedule,courseConflicts} from './timetable';
describe('timetable',()=>{
 it('expands odd weeks and excludes cancelled dates and ended semesters',()=>{const c=syntheticCourses()[2];expect(expandCourses([c],'2026-09-07','2026-09-27').length).toBe(2);c.cancelledDates=['2026-09-09'];expect(expandCourses([c],'2026-09-07','2026-09-27').length).toBe(1);expect(expandCourses([c],'2027-02-01','2027-02-20').length).toBe(0)});
 it('rejects bad periods and leaves ambiguous text unparsed',()=>{expect(parseTimetableText('星期一第一节','2026-09-07','2027-01-10').unparsed).toHaveLength(1);expect(()=>validateCourse({...syntheticCourses()[0],endTime:'07:00'})).toThrow();expect(()=>validateCourse({...syntheticCourses()[0],weekday:0})).toThrow()});
 it('finds course overlaps and never schedules inside a course',()=>{const c=syntheticCourses()[0];expect(courseConflicts([c,{...c,id:'second'}]).length).toBeGreaterThan(0);const r=localSchedule([{id:'t',title:'准备材料',duration_minutes:60,evidence_ids:['block:notice']}],[c],'2026-10-12','2026-10-12');expect(r.suggestions[0].starts_at).toBe('2026-10-12T02:00:00.000Z')});
 it('does not invent duration or evidence to force a slot',()=>{expect(localSchedule([{id:'t',duration_minutes:null,evidence_ids:['b']}],[],'2026-10-12','2026-10-12').unscheduled[0].reason).toBe('duration_required')});
});
