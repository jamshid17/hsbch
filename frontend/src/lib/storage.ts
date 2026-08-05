// Host-assigns draft, stored as { itemId → { personName → quantity } } so it
// survives back-navigation to the people list, where PUT /people reassigns
// all person UUIDs (names are the stable identity across that round-trip).
const PREFIX = "hsbch_v3";

type NameQtyAssignments = Record<string, Record<string, number>>;

export const storage = {
  saveAssignments(sessionId: string, data: NameQtyAssignments) {
    try {
      localStorage.setItem(`${PREFIX}_assign_${sessionId}`, JSON.stringify(data));
    } catch {}
  },

  loadAssignments(sessionId: string): NameQtyAssignments | null {
    try {
      const raw = localStorage.getItem(`${PREFIX}_assign_${sessionId}`);
      return raw ? (JSON.parse(raw) as NameQtyAssignments) : null;
    } catch {
      return null;
    }
  },

  clearAssignments(sessionId: string) {
    localStorage.removeItem(`${PREFIX}_assign_${sessionId}`);
  },
};
