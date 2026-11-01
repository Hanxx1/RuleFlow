export function demoPlan(tasks:any[],edgePairs:string[][]){
  const edges=edgePairs.map(x=>({before_task_id:x[0],after_task_id:x[1]}));
  const by=Object.fromEntries(tasks.map(task=>[task.id,task]));
  const enriched=tasks.map(task=>({...task,duration_minutes:task.duration_minutes??null,materials:task.materials||[],files:[],is_actionable:['todo','in_progress'].includes(task.status)&&edges.filter(edge=>edge.after_task_id===task.id).every(edge=>['done','skipped'].includes(by[edge.before_task_id]?.status))}));
  const completed=enriched.filter(task=>task.status==='done').length;
  return {ordered_tasks:enriched,edges,overall_progress:enriched.length?Math.round(completed*100/enriched.length):0,current_tasks:enriched.filter(task=>task.is_actionable),completed_tasks:completed,pending_tasks:enriched.filter(task=>['todo','in_progress'].includes(task.status)).length};
}
