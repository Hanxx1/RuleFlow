export type Truth = 'TRUE' | 'FALSE' | 'UNKNOWN';
const fields: string[] = ['student_type','enrollment_year','graduation_year','college','major','class_name','role','rank_percent','team_size','certificate_level','moral_bonus_items','moral_score','advisor_count','participation_count','disciplinary_status','coursework_status','fitness_status','school'];
function validFact(key: string, value: Object): boolean {
  if (!fields.includes(key)) return false;
  if (key === 'moral_bonus_items') {
    if (!Array.isArray(value)) return false;
    const list = value as Array<string>;
    return list.length <= 30 && list.every(item => typeof item === 'string' && item.trim().length > 0 && item.length <= 100) && new Set(list).size === list.length;
  }
  if (['enrollment_year','graduation_year','team_size','certificate_level','rank_percent','moral_score','advisor_count','participation_count'].includes(key)) {
    if (typeof value !== 'number' || !Number.isFinite(value as number)) return false;
    const number = value as number;
    if (key === 'rank_percent' || key === 'moral_score') return number >= 0 && number <= 100;
    if (!Number.isInteger(number)) return false;
    if (key === 'team_size') return number >= 1 && number <= 1000;
    if (key === 'moral_score') return number >= 0 && number <= 100;
    if (key === 'advisor_count' || key === 'participation_count') return number >= 0 && number <= 100 && Number.isInteger(number);
    if (key === 'certificate_level') return number >= 0 && number <= 100;
    return number >= 1990 && number <= 2100;
  }
  if (typeof value !== 'string' || (value as string).trim().length === 0 || (value as string).length > 100) return false;
  if (key === 'disciplinary_status') return ['clear','recorded'].includes(value as string);
  if (key === 'coursework_status' || key === 'fitness_status') return ['passed','failed'].includes(value as string);
  return key !== 'student_type' || ['undergraduate','graduate','teacher','other'].includes(value as string);
}
export function evaluate(ast: Record<string, Object>, profile: Record<string, Object>, depth: number = 0): Truth {
  if (depth > 32) return 'UNKNOWN';
  const op = ast['op'] as string;
  if (op === 'and' || op === 'or' || op === 'not') {
    const args = ast['args'] as Array<Record<string, Object>>;
    if (!Array.isArray(args) || args.length === 0 || (op === 'not' && args.length !== 1)) return 'UNKNOWN';
    const values = args.map(child => evaluate(child, profile, depth + 1));
    if (op === 'not') return values[0] === 'TRUE' ? 'FALSE' : values[0] === 'FALSE' ? 'TRUE' : 'UNKNOWN';
    if (op === 'and') return values.includes('FALSE') ? 'FALSE' : values.every(value => value === 'TRUE') ? 'TRUE' : 'UNKNOWN';
    return values.includes('TRUE') ? 'TRUE' : values.every(value => value === 'FALSE') ? 'FALSE' : 'UNKNOWN';
  }
  const field = ast['field'] as string;
  if (typeof field !== 'string' || !field.startsWith('profile.')) return 'UNKNOWN';
  const key = field.replace('profile.',''), actual = profile[key], expected = ast['value'];
  if (actual === undefined || actual === null || !validFact(key,actual)) return 'UNKNOWN';
  if (op === 'exists') return 'TRUE';
  if (op === 'in') {
    if (Array.isArray(actual) || !Array.isArray(expected)) return 'UNKNOWN';
    const choices = expected as Array<Object>;
    if (!choices.length || !choices.every(item => item !== null && validFact(key,item))) return 'UNKNOWN';
    return choices.includes(actual) ? 'TRUE' : 'FALSE';
  }
  if (op === 'contains') {
    if (typeof expected !== 'string') return 'UNKNOWN';
    if (Array.isArray(actual)) return (actual as Array<string>).includes(expected as string) ? 'TRUE' : 'FALSE';
    if (typeof actual === 'string') return (actual as string).includes(expected as string) ? 'TRUE' : 'FALSE';
    return 'UNKNOWN';
  }
  if (expected === null || expected === undefined || !validFact(key,expected)) return 'UNKNOWN';
  if (op === 'eq') return JSON.stringify(actual) === JSON.stringify(expected) ? 'TRUE' : 'FALSE';
  if (typeof actual !== 'number') return 'UNKNOWN';
  let ok = false;
  if (op === 'gte') ok = (actual as number) >= (expected as number);
  else if (op === 'lte') ok = (actual as number) <= (expected as number);
  else if (op === 'before') ok = (actual as number) < (expected as number);
  else if (op === 'after') ok = (actual as number) > (expected as number);
  else return 'UNKNOWN';
  return ok ? 'TRUE' : 'FALSE';
}
