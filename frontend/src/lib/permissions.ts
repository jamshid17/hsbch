/**
 * What an admin may do, as the panel words it.
 *
 * The keys are defined by the backend (app/permissions.py) and carried here
 * by hand, because the labels are Uzbek UI copy and the rest of the panel's
 * copy lives in the frontend too. A backend test pins the key set, so a
 * rename there is a deliberate act rather than a checkbox that silently
 * stops matching anything.
 *
 * These only decide what gets drawn. Every endpoint behind them checks the
 * same grant, so hiding a button is a courtesy, not the lock.
 */
export const PERMISSIONS = [
  {
    key: "subscriptions",
    label: "Obunalar",
    hint: "Obuna yoqish va to'xtatish — bu pul harakati",
  },
  {
    key: "block_users",
    label: "Bloklash",
    hint: "Foydalanuvchini bloklash va blokdan chiqarish",
  },
  { key: "payments", label: "To'lovlar", hint: "To'lovlar tarixi va tushum" },
  { key: "sessions", label: "Sessiyalar", hint: "Bo'lingan hisoblar ro'yxati" },
  { key: "tables", label: "Baza", hint: "Jadvallar va baza hajmi" },
  {
    key: "manage_admins",
    label: "Adminlarni boshqarish",
    hint: "Admin qilish va huquq berish — eng kuchlisi, oxirida bering",
  },
] as const;

export type PermissionKey = (typeof PERMISSIONS)[number]["key"];

export function permissionLabel(key: string): string {
  return PERMISSIONS.find((p) => p.key === key)?.label ?? key;
}

/** Does the signed-in admin hold this grant? */
export function can(
  me: { permissions?: string[] } | undefined,
  key: PermissionKey,
): boolean {
  return !!me?.permissions?.includes(key);
}
