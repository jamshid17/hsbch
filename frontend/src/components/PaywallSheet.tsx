import { useEffect } from "react";
import { useTranslation } from "react-i18next";
import type { MeOut } from "../api";
import Paywall from "./Paywall";

export default function PaywallSheet({ me, onClose }: { me: MeOut; onClose: () => void }) {
  const { t } = useTranslation();

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <>
      <div className="overlay" onClick={onClose} />
      <div className="sheet" role="dialog" aria-modal="true">
        <div className="sheet-handle" />
        <Paywall me={me} />
        <button className="btn btn-ghost" onClick={onClose}>
          {t("paywall.close")}
        </button>
      </div>
    </>
  );
}
