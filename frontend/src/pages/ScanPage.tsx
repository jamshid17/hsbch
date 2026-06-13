import { useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { api } from "../api";
import { getTelegramUser } from "../telegram";

export default function ScanPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const inputRef = useRef<HTMLInputElement>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [scanned, setScanned] = useState<{ sessionId: string; title: string } | null>(null);

  function onFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0];
    if (!f) return;
    setFile(f);
    setPreview(URL.createObjectURL(f));
    setError("");
    setScanned(null);
  }

  async function handleScan() {
    if (!file) return;
    setLoading(true);
    setError("");
    try {
      const { chatId } = getTelegramUser();
      const session = await api.createSession(chatId > 0 ? chatId : undefined);
      const result = await api.uploadReceipt(session.id, file);
      setScanned({ sessionId: session.id, title: result.title });
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : t("scan.scanning"));
    } finally {
      setLoading(false);
    }
  }

  async function handleContinue() {
    if (!scanned) return;
    await api.updateSession(scanned.sessionId, { title: scanned.title });
    navigate(`/edit/${scanned.sessionId}`);
  }

  return (
    <div className="page">
      <h1>{t("scan.title")}</h1>
      <p style={{ color: "var(--hint)", fontSize: 14 }}>{t("scan.subtitle")}</p>

      <div
        className="card"
        style={{ alignItems: "center", minHeight: 200, justifyContent: "center", cursor: scanned ? "default" : "pointer" }}
        onClick={() => !scanned && inputRef.current?.click()}
      >
        {preview ? (
          <img
            src={preview}
            alt="Receipt preview"
            style={{ maxWidth: "100%", maxHeight: 300, borderRadius: 8, objectFit: "contain" }}
          />
        ) : (
          <div style={{ textAlign: "center", color: "var(--hint)" }}>
            <div style={{ fontSize: 48 }}>📷</div>
            <div style={{ marginTop: 8, fontSize: 15 }}>{t("scan.tapToSelect")}</div>
          </div>
        )}
        <input
          ref={inputRef}
          type="file"
          accept="image/*"
          capture="environment"
          onChange={onFileChange}
          style={{ display: "none" }}
        />
      </div>

      {scanned && (
        <div className="card" style={{ gap: 8 }}>
          <div className="label">{t("scan.scannedAs")}</div>
          <input
            type="text"
            value={scanned.title}
            onChange={(e) => setScanned((s) => s ? { ...s, title: e.target.value } : s)}
            style={{ fontWeight: 600, fontSize: 16 }}
          />
        </div>
      )}

      {error && <p className="error">{error}</p>}

      {scanned ? (
        <button className="btn" onClick={handleContinue}>
          {t("scan.continueBtn")}
        </button>
      ) : (
        <button className="btn" disabled={!file || loading} onClick={handleScan}>
          {loading ? t("scan.scanning") : t("scan.scanBtn")}
        </button>
      )}
    </div>
  );
}
