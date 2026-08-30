import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

/** Raccourcit un chemin filesystem en gardant la fin (les segments les
 *  plus significatifs). Évite qu'un long chemin comme
 *  /home/jeremie/Documents/Developpement/pressarr/pressarr/.dev-magazines
 *  fasse déborder un modal ou push la largeur d'un select. Rend
 *  ".../pressarr/.dev-magazines" en fonction de maxLen. */
export function shortenPath(path: string, maxLen = 35): string {
  if (!path) return ''
  if (path.length <= maxLen) return path
  const parts = path.split('/')
  let short = parts[parts.length - 1]
  for (let i = parts.length - 2; i >= 0; i--) {
    const candidate = parts[i] + '/' + short
    if (candidate.length + 4 > maxLen) break
    short = candidate
  }
  return '.../' + short
}
