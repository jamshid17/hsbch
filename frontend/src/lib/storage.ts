// Assignments stored as { itemId → personName[] } so they survive
// back-navigation where PUT /people reassigns all person UUIDs.

const PREFIX = "hsbch";

type NameAssignments = Record<string, string[]>;

export const storage = {
  saveAssignments(sessionId: string, data: NameAssignments) {
    try {
      localStorage.setItem(`${PREFIX}_assign_${sessionId}`, JSON.stringify(data));
    } catch {}
  },

  loadAssignments(sessionId: string): NameAssignments | null {
    try {
      const raw = localStorage.getItem(`${PREFIX}_assign_${sessionId}`);
      return raw ? (JSON.parse(raw) as NameAssignments) : null;
    } catch {
      return null;
    }
  },

  clearAssignments(sessionId: string) {
    localStorage.removeItem(`${PREFIX}_assign_${sessionId}`);
  },
};
