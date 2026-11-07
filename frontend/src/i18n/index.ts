import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'
import en from './en.json'
import fr from './fr.json'

export const LANGUAGES = ['en', 'fr'] as const
export type Language = (typeof LANGUAGES)[number]
const STORAGE_KEY = 'pressarr.language'

/** The interface's language: the one chosen in Settings → General (kept in this browser),
 * else the browser's own when Pressarr speaks it, else English. */
function initialLanguage(): Language {
  try {
    const saved = localStorage.getItem(STORAGE_KEY)
    if (saved && (LANGUAGES as readonly string[]).includes(saved)) return saved as Language
  } catch {
    // storage blocked (private window): the browser's language decides
  }
  const browser = (navigator.language || 'en').slice(0, 2).toLowerCase()
  return (LANGUAGES as readonly string[]).includes(browser) ? (browser as Language) : 'en'
}

export function setLanguage(language: Language) {
  try {
    localStorage.setItem(STORAGE_KEY, language)
  } catch {
    // not kept, still applied for this visit
  }
  void i18n.changeLanguage(language)
}

i18n.use(initReactI18next).init({
  resources: { en: { translation: en }, fr: { translation: fr } },
  lng: initialLanguage(),
  fallbackLng: 'en',
  interpolation: { escapeValue: false },
})

export default i18n
