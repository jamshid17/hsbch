import { useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import { api, ApiError } from "../api";
import {
  ACCEPT_ATTR,
  ImageTooLargeError,
  compressImage,
  isAcceptedImage,
} from "../lib/image";
import { haptic } from "../telegram";
import Paywall from "../components/Paywall";

export default function ScanPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const inputRef = useRef<HTMLInputElement>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [quotaExceeded, setQuotaExceeded] = useState(false);

  const { data: me } = useQuery({
    queryKey: ["me"],
    queryFn: () => api.getMe(),
  });

  function onFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0];
    // Reset the input either way, so picking the same file again after an
    // error still fires a change event.
    e.target.value = "";
    if (!f) return;

    // The accept attribute is a hint, not a rule — desktop pickers and some
    // Android file managers hand over PDFs regardless. Refuse here so nothing
    // is uploaded and no session is created for a file that can never scan.
    if (!isAcceptedImage(f)) {
      setPreview(null);
      setError(t("scan.notAnImage"));
      return;
    }

    // Retries pick a new photo; the previous blob has no reader left.
    setPreview((old) => {
      if (old) URL.revokeObjectURL(old);
      return URL.createObjectURL(f);
    });
    setError("");
    setQuotaExceeded(false);
    // Picking the photo is the decision; there was never a second one to make
    // on this screen, so scanning starts on the same tap.
    scan(f);
  }

  async function scan(file: File) {
    setLoading(true);
    setError("");
    setQuotaExceeded(false);
    try {
      // Compress before the session exists: a photo that can't be shrunk under
      // the limit shouldn't leave an empty session behind.
      const image = await compressImage(file);
      const session = await api.createSession();
      await api.uploadReceipt(session.id, image);
      haptic.success();
      navigate(`/edit/${session.id}`);
    } catch (e: unknown) {
      haptic.error();
      if (e instanceof ImageTooLargeError) {
        setError(t("scan.tooLarge"));
      } else if (e instanceof ApiError && e.status === 402) {
        setQuotaExceeded(true);
        setError(e.message);
      } else if (e instanceof ApiError && (e.status === 413 || e.status === 415)) {
        setError(e.message);
      } else {
        setError(e instanceof Error ? e.message : t("scan.failed"));
      }
      setLoading(false);
    }
  }

  // Out of free scans: the picker never appears, so nobody burns a photo on a
  // request the server would reject with 402 anyway. Nothing is locked while
  // the paid tier is switched off.
  const locked =
    !!me && me.subscriptions_enabled && !me.is_subscribed && me.scans_left === 0;

  if (locked && me) {
    return (
      <div className="page">
        <h1>{t("scan.title")}</h1>
        <Paywall me={me} />
        <button className="btn btn-ghost" onClick={() => navigate("/")}>
          {t("paywall.back")}
        </button>
      </div>
    );
  }

  const pick = () => {
    if (loading) return;
    haptic.select();
    inputRef.current?.click();
  };

  return (
    <div className="page">
      <h1>{t("scan.title")}</h1>
      <p style={{ color: "var(--hint)", fontSize: 14 }}>{t("scan.subtitle")}</p>

      <div
        className="card scan-drop"
        role="button"
        tabIndex={0}
        aria-busy={loading}
        aria-label={t("scan.tapToSelect")}
        onClick={pick}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            pick();
          }
        }}
      >
        {preview ? (
          <img
            src={preview}
            alt=""
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
          accept={ACCEPT_ATTR}
          onChange={onFileChange}
          style={{ display: "none" }}
        />
      </div>

      {/* Scanning takes a few seconds and there is nothing to do meanwhile —
          the status replaces the button rather than sitting next to it. */}
      {loading && (
        <div className="scan-status" role="status">
          <div className="auth-spinner" />
          <span>{t("scan.scanning")}</span>
        </div>
      )}

      {error && <p className="error">{error}</p>}
      {quotaExceeded && me && me.subscriptions_enabled && !me.is_subscribed && (
        <Paywall me={me} />
      )}

      {!loading && (
        <button className="btn" onClick={pick}>
          {preview ? t("scan.retry") : t("scan.pickBtn")}
        </button>
      )}
    </div>
  );
}
