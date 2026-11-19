import {describe, expect, it} from 'vitest';
import {emptyWorkspace, exportWorkspace} from '../../services/clientWorkspace';
import {expandCourses, parseTimetableText, localSchedule} from '../../services/timetable';
import {layoutDays} from '../planning/scheduleGrid';
import {previewCourseRestore, summarizeCourseRestore} from './courseRestorePreview';

const monday = '2026-11-09';
const wednesday = '2026-11-11';
function courseRules() {
  return parseTimetableText(
    '合成线代 周一 09:00-10:00 第1-2周\n合成线代 周三 14:00-15:00 第1-2周',
    monday, '2026-11-22',
  ).courses;
}

describe('CM-006 课程时间与恢复样例', () => {
  it('单次取消只移除命中规则的当次发生，保留其他时段及原句', () => {
    const [mon, wed] = courseRules();
    const blocks = expandCourses([{...mon, cancelledDates: [monday]}, wed], monday, '2026-11-22');
    expect(blocks.map(b => [b.id, b.evidence_ids])).toEqual([
      [wed.id + ':' + wednesday, [wed.evidence.id]],
      [mon.id + ':2026-11-16', [mon.evidence.id]],
      [wed.id + ':2026-11-18', [wed.evidence.id]],
    ]);
  });

  it('缺少发生映射时，同名同刻的两条来源在网格中仍可分别核对', () => {
    const [local] = expandCourses(courseRules(), monday, monday);
    const remote = {...local, id: 'server-course-1', evidence_ids: ['block:server-demo']};
    const {days, errors} = layoutDays([local, remote], [monday]);
    expect(errors).toEqual([]);
    expect(days[0].segments).toHaveLength(2);
    expect(days[0].segments.map(s => [s.item.id, s.item.evidence_ids, s.conflict])).toEqual(expect.arrayContaining([
      [local.id, local.evidence_ids, true], [remote.id, remote.evidence_ids, true],
    ]));
  });

  it('旧备份预览保留当前占用，分别按两版规则重算时只有获选版本影响任务时间', () => {
    const backup = emptyWorkspace('cm006-demo');
    backup.revision = 3;
    backup.courses = courseRules();
    const [mon, wed] = backup.courses;
    const current = {...backup, revision: 4, courses: [
      {...mon, startTime: '08:00', evidence: {id: 'block:client:edit', text: '合成更正：周一 08:00–10:00'}},
      {...wed, cancelledDates: [wednesday]},
    ]};
    const before = exportWorkspace(current);
    const raw = exportWorkspace(backup);
    const preview = previewCourseRestore(raw, current);
    expect(preview.timetableCount).toBe(2);
    expect(exportWorkspace(current)).toBe(before);
    expect(() => summarizeCourseRestore(preview, {...current, revision: 5}, [], 'replace')).toThrow('重新预览');
    const task = {id: 'demo-task', duration_minutes: 60, evidence_ids: ['block:client:task']};
    for (const [workspace, expectedDays, firstSlot] of [
      [current, [monday], '2026-11-09T02:00:00.000Z'],
      [backup, [monday, wednesday], '2026-11-09T00:00:00.000Z'],
    ] as const) {
      expect(expandCourses(workspace.courses, monday, wednesday).map(b => b.starts_at.slice(0, 10))).toEqual(expectedDays);
      expect(localSchedule([task], workspace.courses, monday, monday).suggestions[0]?.starts_at).toBe(firstSlot);
    }
    expect(exportWorkspace(backup)).toBe(raw);
    expect(exportWorkspace(current)).toBe(before);
  });
});
