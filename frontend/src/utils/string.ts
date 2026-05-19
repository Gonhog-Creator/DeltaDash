/**
 * Normalize a string for display
 * - Capitalize first letter
 * - Replace underscores with spaces
 * - Capitalize each word
 * - Keep specific acronyms in all caps (UHMWPE)
 */
export function normalizeString(str: string): string {
  if (!str) return str;

  const allCapsAcronyms = ['UHMWPE'];

  return str
    .replace(/_/g, ' ')  // Replace underscores with spaces
    .split(' ')
    .map(word => {
      const upperWord = word.toUpperCase();
      if (allCapsAcronyms.includes(upperWord)) {
        return upperWord;
      }
      return word.charAt(0).toUpperCase() + word.slice(1).toLowerCase();
    })
    .join(' ');
}

/**
 * Normalize a string to title case
 * - Capitalize first letter of each word
 * - Lowercase the rest
 */
export function toTitleCase(str: string): string {
  if (!str) return str;
  
  return str
    .toLowerCase()
    .split(' ')
    .map(word => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
}
