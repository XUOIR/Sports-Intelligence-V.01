// The API serializes every instant in America/Vancouver. Preserve those wall-clock components
// even when the user's browser has timezone rules older than BC's 2026 transition.
export function pacificTime(value) {
  if(!/[+-]\d{2}:\d{2}$/.test(value))return 'Time unavailable';
  return new Intl.DateTimeFormat('en-CA',{timeZone:'UTC',month:'short',day:'numeric',hour:'numeric',minute:'2-digit'}).format(new Date(value.replace(/[+-]\d{2}:\d{2}$/,'Z')));
}
