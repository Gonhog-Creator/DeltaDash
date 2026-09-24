/**
 * Conditioning helpers.
 *
 * Conditioning is stored per-shot. All shots on one side of a vest share the
 * same conditioning, but front and back can differ. A session-level combined
 * value is stored as "ambient" (same on both sides) or "ambient/wet"
 * (front/back) for display purposes.
 */

export const CONDITIONING_OPTIONS = ['ambient', 'wet', 'tumbled', 'ballistic_limit'];

const FRONT_SIDES = new Set(['front', 'frente']);
const BACK_SIDES = new Set(['back', 'espalda']);

export const isFrontSide = (side?: string | null) => !!side && FRONT_SIDES.has(side.toLowerCase());
export const isBackSide = (side?: string | null) => !!side && BACK_SIDES.has(side.toLowerCase());

/**
 * Format a conditioning value for display.
 * Handles single values ('ambient' -> 'Ambient'), underscores
 * ('ballistic_limit' -> 'Ballistic Limit') and combined front/back values
 * ('ambient/wet' -> 'Ambient/Wet').
 */
export function formatConditioning(value: string | null | undefined): string {
  if (!value) return '-';
  return value
    .split('/')
    .map((part) =>
      part
        .replace(/_/g, ' ')
        .split(' ')
        .map((word) => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
        .join(' ')
    )
    .join('/');
}

const CONDITIONING_DISPLAYS = CONDITIONING_OPTIONS.map(formatConditioning);

interface SideShot {
  id: string;
  side?: string | null;
  conditioning?: string | null;
}

/**
 * The unique conditioning value used by shots on one side, or null when that
 * side has no shots / no conditioning / mixed values.
 */
export function sideConditioning(shots: { side?: string | null; conditioning?: string | null }[], side: 'front' | 'back'): string | null {
  const matches = shots.filter((s) => (side === 'front' ? isFrontSide(s.side) : isBackSide(s.side)));
  const unique = [...new Set(matches.map((s) => s.conditioning).filter((c): c is string => !!c))];
  return unique.length === 1 ? unique[0] : null;
}

/** Combine front/back picks into a single stored value: 'ambient' or 'ambient/wet'. */
export function combineSideConditioning(front: string | null, back: string | null): string | null {
  if (front && back) return front === back ? front : `${front}/${back}`;
  return front || back || null;
}

/**
 * Combined session-level conditioning from the user's front/back picks.
 * Only sides that actually have shots contribute.
 */
export function sessionConditioningFromSides(
  shots: { side?: string | null }[],
  front: string | null,
  back: string | null
): string | null {
  const f = shots.some((s) => isFrontSide(s.side)) ? front : null;
  const b = shots.some((s) => isBackSide(s.side)) ? back : null;
  return combineSideConditioning(f, b);
}

/**
 * Shots whose conditioning differs from the target value for their side.
 * Shots without a front/back side are left untouched.
 */
export function conditioningShotUpdates(
  shots: SideShot[],
  front: string | null,
  back: string | null
): { id: string; conditioning: string | null }[] {
  return shots.flatMap((shot) => {
    const target = isFrontSide(shot.side) ? front : isBackSide(shot.side) ? back : undefined;
    if (target === undefined || shot.conditioning === target) return [];
    return [{ id: shot.id, conditioning: target }];
  });
}

/**
 * Replace the trailing " - Conditioning" segment of an auto-generated session
 * name (e.g. "1 - S - Ambient" -> "1 - S - Ambient/Wet"). Names whose last
 * segment isn't a conditioning value are returned unchanged.
 */
export function withConditioningInName(name: string, conditioningDisplay: string): string {
  const parts = name.split(' - ');
  if (parts.length < 2) return name;
  const last = parts[parts.length - 1];
  const isConditioningSegment = last.split('/').every((p) => CONDITIONING_DISPLAYS.includes(p));
  if (!isConditioningSegment) return name;
  if (!conditioningDisplay) return parts.slice(0, -1).join(' - ');
  return [...parts.slice(0, -1), conditioningDisplay].join(' - ');
}
