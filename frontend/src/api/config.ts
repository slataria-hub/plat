/**
 * Base URL for API.
 * - Browser local: empty → same origin + Vite proxy
 * - Capacitor APK: set VITE_API_URL at build time, e.g. https://your-api.onrender.com
 */
export const API_ORIGIN =
  (typeof import.meta !== 'undefined' && (import.meta as any).env?.VITE_API_URL) || ''
