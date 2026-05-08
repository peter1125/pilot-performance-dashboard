export function filterPointsByWindow(points, windowKey) {
  if (!Array.isArray(points) || points.length === 0 || windowKey === 'all') return points || [];
  const hours = Number(String(windowKey).replace('h', ''));
  if (!Number.isFinite(hours) || hours <= 0) return points;
  const latestMs = new Date(points[points.length - 1].time).getTime();
  const cutoff = latestMs - hours * 60 * 60 * 1000;
  return points.filter((point) => new Date(point.time).getTime() >= cutoff);
}

export function nearestPointIndex(xs, x) {
  if (!Array.isArray(xs) || xs.length === 0) return -1;
  let bestIndex = 0;
  let bestDistance = Math.abs(xs[0] - x);
  for (let i = 1; i < xs.length; i += 1) {
    const distance = Math.abs(xs[i] - x);
    if (distance < bestDistance) {
      bestDistance = distance;
      bestIndex = i;
    }
  }
  return bestIndex;
}
