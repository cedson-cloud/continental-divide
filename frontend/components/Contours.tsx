type Peak = { cx: number; cy: number; r0: number };

// Seeded (mulberry32) so the server render and the client hydrate draw identical lines.
function seeded(seed: number): () => number {
  return () => {
    seed = (seed + 0x6d2b79f5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function contourPaths(peaks: Peak[], rings: number, gap: number, seed: number): string[] {
  const random = seeded(seed);
  const paths: string[] = [];
  for (const { cx, cy, r0 } of peaks) {
    const phase = [random() * 6.3, random() * 6.3, random() * 6.3];
    for (let i = 0; i < rings; i++) {
      const radius = r0 + i * gap;
      let d = "";
      for (let k = 0; k <= 120; k++) {
        const a = (k / 120) * Math.PI * 2;
        const r =
          radius *
          (1 +
            0.13 * Math.sin(2 * a + phase[0]) +
            0.07 * Math.sin(3 * a + phase[1] + i * 0.18) +
            0.035 * Math.sin(5 * a + phase[2] - i * 0.1));
        d += `${k ? "L" : "M"}${(cx + r * Math.cos(a)).toFixed(1)} ${(cy + r * 0.7 * Math.sin(a)).toFixed(1)}`;
      }
      paths.push(`${d}Z`);
    }
  }
  return paths;
}

const SIDEBAR_PATHS = contourPaths(
  [
    { cx: 90, cy: 250, r0: 14 },
    { cx: 270, cy: 330, r0: 30 },
  ],
  11,
  15,
  7,
);

export function SidebarContours() {
  return (
    <svg
      className="sidebar-contours"
      viewBox="0 0 320 340"
      preserveAspectRatio="xMidYMid slice"
      fill="none"
      stroke="currentColor"
      strokeWidth={1}
      aria-hidden="true"
      focusable="false"
    >
      {SIDEBAR_PATHS.map((d, i) => (
        <path key={i} d={d} />
      ))}
    </svg>
  );
}
