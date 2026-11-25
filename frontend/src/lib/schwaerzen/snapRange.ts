/**
 * The PDF only tells us how wide a whole text item is, not where each letter sits. A keyword in the middle of a longer item
 * ("(AFR-Q-VPV)") is therefore first ESTIMATED (and that estimate can be off by more than half a character, e.g. in a
 * typewriter font where every letter is equally wide).
 *
 * This function makes it EXACT by counting: the ink of the line is split into letter groups (runs of columns with ink,
 * separated by empty columns). If there are exactly as many groups as there are visible characters, character k IS group k,
 * and the keyword's boundaries are the centres of the gaps right before its first and right after its last group.
 * If the numbers differ (letters touch, e.g. "(A" or "VA"), nothing is guessed: the caller keeps the generous estimate.
 * A keyword is therefore never cut by a wrong guess.
 */

export interface ClusterInput {
  /** Per pixel column: number of ink pixels in the letter band of that column. Column 0 lies at x = originPt. */
  ink: ArrayLike<number>;
  originPt: number;
  pxPerPt: number;
  /** The characters of the whole text item (spaces included) and the keyword's range [from, to) in it. */
  chars: string;
  from: number;
  to: number;
  /** Bounds of the whole item (pt): the outer boundary when the keyword starts/ends the item. */
  itemX0: number;
  itemX1: number;
}

export interface ClusterResult {
  start: number;
  end: number;
}

/** Runs of columns that contain ink: [firstColumn, lastColumn] (inclusive). */
export function inkClusters(ink: ArrayLike<number>): [number, number][] {
  const out: [number, number][] = [];
  let start = -1;
  for (let i = 0; i <= ink.length; i++) {
    const has = i < ink.length && ink[i]! > 0;
    if (has && start < 0) start = i;
    else if (!has && start >= 0) {
      out.push([start, i - 1]);
      start = -1;
    }
  }
  return out;
}

const isBlank = (ch: string) => /\s/u.test(ch);

/**
 * Exact boundaries of the keyword, or null if the letter groups cannot be matched one-to-one with the characters.
 */
export function clusterBoundaries(input: ClusterInput): ClusterResult | null {
  const { chars, from, to, originPt, pxPerPt, itemX0, itemX1 } = input;
  const all = [...chars];
  const visible = all.filter((c) => !isBlank(c)).length;
  const clusters = inkClusters(input.ink);
  if (visible === 0 || clusters.length !== visible) return null;

  // index of the keyword's first/last visible character among the visible ones
  const before = (n: number) => all.slice(0, n).filter((c) => !isBlank(c)).length;
  const first = before(from);
  const last = before(to) - 1;
  if (last < first || first < 0 || last >= visible) return null;

  const x = (col: number) => originPt + col / pxPerPt;
  // boundary = centre of the empty gap between two neighbouring groups; at the item's end: its edge
  const startX =
    first === 0 ? Math.min(itemX0, x(clusters[0]![0]) - 0.1) : (x(clusters[first - 1]![1] + 1) + x(clusters[first]![0])) / 2;
  const endX =
    last === visible - 1
      ? Math.max(itemX1, x(clusters[last]![1] + 1) + 0.1)
      : (x(clusters[last]![1] + 1) + x(clusters[last + 1]![0])) / 2;
  if (!(endX > startX)) return null;
  return { start: startX, end: endX };
}
