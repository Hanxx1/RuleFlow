"""Deterministic task scheduling over persisted availability blocks."""
from __future__ import annotations

import heapq
import math
from datetime import date, datetime, time, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


WORK_START = time(8, 0)
WORK_END = time(21, 0)
DEFAULT_SLOT_MINUTES = 30


def timezone_for(name: str):
    if name == "Asia/Shanghai":
        return timezone(timedelta(hours=8), name)
    if name == "UTC":
        return timezone.utc
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError as exc:
        raise ValueError("timezone 无效") from exc


def parse_instant(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("时间必须是 ISO-8601 格式") from exc
    if parsed.tzinfo is None:
        raise ValueError("时间必须包含时区")
    return parsed


def utc_iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _ceil_slot(value: datetime, minutes: int = DEFAULT_SLOT_MINUTES) -> datetime:
    if value.second or value.microsecond:
        value += timedelta(minutes=1)
    value = value.replace(second=0, microsecond=0)
    remainder = value.minute % minutes
    if remainder:
        value += timedelta(minutes=minutes - remainder)
    return value


def _deadline(value: str | None, tz) -> datetime | None:
    if not value:
        return None
    try:
        if len(value) == 10:
            parsed_date = date.fromisoformat(value)
            return datetime.combine(parsed_date, time(23, 59, 59), tzinfo=tz)
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.replace(tzinfo=tz) if parsed.tzinfo is None else parsed.astimezone(tz)
    except ValueError:
        return None


def task_deadline(value: str | None) -> datetime | None:
    """Date-only tasks use Shanghai day-end; explicit offsets keep their instant."""
    return _deadline(value, timezone_for('Asia/Shanghai'))


def _sort_tasks(tasks: list[dict[str, Any]], edges: list[dict[str, Any]], tz):
    by_id = {item["id"]: item for item in tasks}
    indegree = {item["id"]: 0 for item in tasks}
    successors = {item["id"]: [] for item in tasks}
    for edge in edges:
        before, after = edge["before_task_id"], edge["after_task_id"]
        if after not in by_id:
            continue
        if before in by_id:
            indegree[after] += 1
            successors[before].append(after)

    def priority(task_id: str):
        deadline = task_deadline(by_id[task_id].get("deadline"))
        return (-by_id[task_id].get('priority_score',0),deadline or datetime.max.replace(tzinfo=tz), by_id[task_id]["case_id"], task_id)

    ready = [priority(task_id) + (task_id,) for task_id, count in indegree.items() if count == 0]
    heapq.heapify(ready)
    ordered = []
    while ready:
        *_priority, task_id = heapq.heappop(ready)
        ordered.append(by_id[task_id])
        for successor in sorted(successors[task_id]):
            indegree[successor] -= 1
            if indegree[successor] == 0:
                heapq.heappush(ready, priority(successor) + (successor,))
    if len(ordered) != len(tasks):
        raise ValueError("任务依赖图存在环")
    return ordered


def _first_slot(
    earliest: datetime,
    latest: datetime,
    duration: timedelta,
    occupied: list[tuple[datetime, datetime]],
    tz,
    preferences=None,
    day_minutes=None,
) -> tuple[datetime, datetime] | None:
    preferences = preferences or {}
    work_start = time(preferences.get('work_start_hour',8))
    work_end = time(preferences.get('work_end_hour',21))
    day_minutes = day_minutes or {}
    cursor = _ceil_slot(earliest.astimezone(tz))
    while cursor + duration <= latest.astimezone(tz):
        day_open = datetime.combine(cursor.date(), work_start, tzinfo=tz)
        day_close = datetime.combine(cursor.date(), work_end, tzinfo=tz)
        if cursor < day_open:
            cursor = day_open
        if cursor + duration > latest.astimezone(tz):
            return None
        if cursor + duration > day_close or day_minutes.get(cursor.date(),0)+duration.total_seconds()/60 > preferences.get('daily_max_minutes',780):
            cursor = datetime.combine(cursor.date() + timedelta(days=1), work_start, tzinfo=tz)
            continue
        end = cursor + duration
        conflict = next(
            (
                (start, finish)
                for start, finish in sorted(occupied)
                if cursor.astimezone(timezone.utc) < finish
                and end.astimezone(timezone.utc) > start
            ),
            None,
        )
        if not conflict:
            return cursor, end
        cursor = _ceil_slot(conflict[1].astimezone(tz))
    return None


def preview_schedule(
    tasks: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    existing_items: list[dict[str, Any]],
    window_start: datetime,
    window_end: datetime,
    timezone_name: str,
    all_task_statuses: dict[str, str],
    preferences: dict | None = None,
    *,
    all_task_durations: dict[str, int | None] | None = None,
) -> dict[str, Any]:
    if window_end <= window_start:
        raise ValueError("window_end 必须晚于 window_start")
    if window_end-window_start>timedelta(days=90):raise ValueError('排程窗口最多90天')
    if len(tasks)>1000:raise ValueError('一次最多预览1000个任务')
    tz = timezone_for(timezone_name)
    preferences = preferences or {}
    start_hour,end_hour = preferences.get('work_start_hour',8),preferences.get('work_end_hour',21)
    if not (isinstance(start_hour,int) and isinstance(end_hour,int) and 0<=start_hour<end_hour<=23):raise ValueError('工作时段须为同一天有效小时范围')
    buffer = timedelta(minutes=preferences.get('buffer_minutes',0))
    if not 0<=buffer.total_seconds()/60<=120 or not 30<=preferences.get('daily_max_minutes',780)<=1380:raise ValueError('缓冲或每日任务时长无效')
    # Scores order ready tasks only. Dependencies/deadlines remain hard constraints.
    tasks=[dict(task) for task in tasks]
    successors={task['id']:set() for task in tasks}
    for edge in edges:
        if edge['before_task_id'] in successors:successors[edge['before_task_id']].add(edge['after_task_id'])
    for task in tasks:
        descendants=set();pending=list(successors.get(task['id'],()))
        while pending:
            child=pending.pop()
            if child in descendants:continue
            descendants.add(child);pending.extend(successors.get(child,()))
        deadline=task_deadline(task.get('deadline'))
        urgency=1/(1+max(0,(deadline-window_start).total_seconds()/86400)/7) if deadline else 0
        dependency_pressure=len(descendants)/max(1,len(tasks)-1)
        task['priority_score']=round(.4*urgency+.3*task.get('importance',0)+.15*dependency_pressure+.15*task.get('preference',0),6)
    ordered = _sort_tasks(tasks, edges, tz)
    occupied = [
        (parse_instant(item["starts_at"]).astimezone(timezone.utc)-buffer, parse_instant(item["ends_at"]).astimezone(timezone.utc)+buffer)
        for item in existing_items
    ]
    existing_task_ends={};existing_minutes={}
    for item in existing_items:
        if item.get('task_id'):
            tid=item['task_id'];end=parse_instant(item['ends_at'])
            existing_task_ends[tid]=max(end,existing_task_ends.get(tid,end))
            existing_minutes[tid]=existing_minutes.get(tid,0)+(end-parse_instant(item['starts_at'])).total_seconds()/60
    day_minutes = {}
    for item in existing_items:
        if item.get('kind')=='task':
            start,end = parse_instant(item['starts_at']).astimezone(tz),parse_instant(item['ends_at']).astimezone(tz)
            while start<end:
                boundary=min(end,datetime.combine(start.date()+timedelta(days=1),time(),tzinfo=tz))
                day_minutes[start.date()]=day_minutes.get(start.date(),0)+(boundary-start).total_seconds()/60
                start=boundary
    predecessor_map: dict[str, list[str]] = {item["id"]: [] for item in tasks}
    for edge in edges:
        if edge["after_task_id"] in predecessor_map:
            predecessor_map[edge["after_task_id"]].append(edge["before_task_id"])

    all_task_durations = all_task_durations or {}
    selected_ids = {task["id"] for task in tasks}
    proposed_ends: dict[str, datetime] = {}
    failed: set[str] = set()
    suggestions = []
    unscheduled = []
    for task in ordered:
        task_id = task["id"]
        needed=int(math.ceil(int(task.get('duration_minutes') or DEFAULT_SLOT_MINUTES)/DEFAULT_SLOT_MINUTES)*DEFAULT_SLOT_MINUTES)
        if task_id in existing_task_ends and (existing_minutes[task_id]>=needed or not task.get('splittable')):
            unscheduled.append(
                {"task_id": task_id, "title": task["title"], "reason": "already_scheduled", "detail": "任务已有日程安排"}
            )
            if existing_minutes[task_id]>=needed:proposed_ends[task_id] = existing_task_ends[task_id]
            continue
        blockers = []
        earliest = window_start
        for predecessor in predecessor_map.get(task_id, []):
            status = all_task_statuses.get(predecessor)
            if status in {"done", "skipped"}:
                continue
            if predecessor in proposed_ends:
                earliest = max(earliest, proposed_ends[predecessor])
            elif (
                predecessor not in selected_ids
                and predecessor in existing_task_ends
                and predecessor in all_task_durations
                and existing_minutes[predecessor] >= (all_task_durations[predecessor] or DEFAULT_SLOT_MINUTES)
            ):
                earliest = max(earliest, existing_task_ends[predecessor])
            else:
                blockers.append(predecessor)
        if blockers or any(item in failed for item in predecessor_map.get(task_id, [])):
            failed.add(task_id)
            unscheduled.append(
                {"task_id": task_id, "title": task["title"], "reason": "blocked_by_predecessor", "detail": "前置任务尚未完成、已有安排时长不足或无法安排"}
            )
            continue

        deadline = task_deadline(task.get("deadline"))
        if task.get("deadline") and deadline is None:
            failed.add(task_id)
            unscheduled.append(
                {"task_id": task_id, "title": task["title"], "reason": "invalid_deadline", "detail": "任务截止时间格式无效"}
            )
            continue
        latest = min(window_end, deadline) if deadline else window_end
        if latest <= earliest:
            failed.add(task_id)
            reason = "deadline_passed" if deadline and deadline <= window_start else "outside_preview_window"
            unscheduled.append(
                {"task_id": task_id, "title": task["title"], "reason": reason, "detail": "截止时间早于可安排时段"}
            )
            continue
        duration_minutes = int(task.get("duration_minutes") or DEFAULT_SLOT_MINUTES)
        rounded_minutes = int(math.ceil(max(0,needed-existing_minutes.get(task_id,0))/30)*30)
        original_occupied=list(occupied);original_day=dict(day_minutes);segments=[];remaining=rounded_minutes
        while remaining:
            sizes=[remaining]
            if task.get('splittable'):
                minimum=task.get('min_chunk_minutes',30);maximum=task.get('max_chunk_minutes',60)
                if minimum%30 or maximum%30 or not 30<=minimum<=maximum<=240:raise ValueError('分段长度须为30分钟倍数且范围有效')
                sizes=list(range(min(maximum,remaining),minimum-1,-30))
                if remaining<minimum:sizes=[]
            possible=[]
            for size in sizes:
                slot=_first_slot(earliest,latest,timedelta(minutes=size),occupied,tz,preferences,day_minutes)
                if slot:possible.append((slot[0],-size,slot[1]))
            if not possible:break
            start,negative_size,end=min(possible);size=-negative_size
            occupied.append((start.astimezone(timezone.utc)-buffer,end.astimezone(timezone.utc)+buffer))
            day_minutes[start.date()]=day_minutes.get(start.date(),0)+size
            segments.append((start,end,size));remaining-=size;earliest=end
        if remaining:
            occupied[:]=original_occupied;day_minutes.clear();day_minutes.update(original_day)
            failed.add(task_id)
            unscheduled.append(
                {"task_id": task_id, "title": task["title"], "reason": "no_available_slot", "detail": "可用时段不足，调整耗时、拆分或规划窗口后重新预览",'required_minutes':rounded_minutes,'available_minutes':rounded_minutes-remaining}
            )
            continue
        proposed_ends[task_id] = max(segments[-1][1],existing_task_ends.get(task_id,segments[-1][1]))
        for index,(start,end,size) in enumerate(segments):
         suggestions.append(
            {
                "task_id": task_id,
                "case_id": task["case_id"],
                "title": task["title"],
                "kind": "task",
                "starts_at": utc_iso(start),
                "ends_at": utc_iso(end),
                "duration_minutes": duration_minutes,
                "scheduled_minutes": size,
                'segment_index':index+1,'segment_count':len(segments),'splittable':bool(task.get('splittable')),'priority_score':task['priority_score'],
                "reason": "earliest_available",
            }
        )
    return {
        "timezone": timezone_name,
        "window_start": utc_iso(window_start),
        "window_end": utc_iso(window_end),
        "suggestions": suggestions,
        "unscheduled": unscheduled,
        "considered_blocks": len(existing_items),
        "preferences": preferences,
    }
