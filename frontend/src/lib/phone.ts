/**
 * Players log in with their phone number (owner, 2026-11-23): it is their username, kept as
 * digits only so 508-555-1234, (508) 555 1234 and +1 508 555 1234 are the same login. Text
 * with letters stays as typed (logins an admin set before, like "aalay").
 */
export function loginName(value: string): string {
  const text = value.trim()
  if (!/^[\d\s().+-]+$/.test(text)) return text
  const digits = text.replace(/\D/g, '')
  return digits.length === 11 && digits.startsWith('1') ? digits.slice(1) : digits
}

/** A 10-digit phone number once cleaned up. */
export const isPhone = (value: string) => /^\d{10}$/.test(loginName(value))
