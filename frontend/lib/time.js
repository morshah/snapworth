import { useEffect, useState } from 'react';

// Backend timestamps are naive UTC. Append 'Z' so the browser parses them as
// UTC (not local time). Epoch math below is timezone-independent.
export function toDate(s) {
  if (!s) return null;
  return new Date(/[Z+]/.test(s) ? s : `${s}Z`);
}

export function formatDuration(seconds) {
  const sec = Math.max(0, Math.floor(seconds));
  const m = Math.floor(sec / 60);
  const s = sec % 60;
  return `${m}:${String(s).padStart(2, '0')}`;
}

// Seconds between start and (end || now). `now` is epoch ms from useNow().
export function elapsed(startIso, endIso, now) {
  const start = toDate(startIso);
  if (!start) return 0;
  const end = endIso ? toDate(endIso).getTime() : now;
  return (end - start.getTime()) / 1000;
}

// Re-renders once per second while `active` so live timers tick.
export function useNow(active = true) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!active) return undefined;
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, [active]);
  return now;
}
