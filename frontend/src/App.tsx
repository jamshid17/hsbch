import { useEffect } from "react";
import { Routes, Route, Navigate, useLocation, useNavigate } from "react-router-dom";
import { tg } from "./telegram";
import EntryPage from "./pages/EntryPage";
import ScanPage from "./pages/ScanPage";
import EditItemsPage from "./pages/EditItemsPage";
import ModePage from "./pages/ModePage";
import JoinPage from "./pages/JoinPage";
import PickPage from "./pages/PickPage";
import HostLivePage from "./pages/HostLivePage";
import PeoplePage from "./pages/PeoplePage";
import AssignPage from "./pages/AssignPage";
import SummaryPage from "./pages/SummaryPage";
import ProgressSteps from "./components/ProgressSteps";
import LanguageSwitcher from "./components/LanguageSwitcher";
import "./app.css";

// Show the native Telegram back button on every screen except the home/entry
// page, and navigate back through history when it's tapped.
function useTelegramBackButton() {
  const { pathname } = useLocation();
  const navigate = useNavigate();

  useEffect(() => {
    const back = tg.BackButton;
    if (!back) return;

    if (pathname === "/") {
      back.hide();
      return;
    }

    const onBack = () => navigate(-1);
    back.onClick(onBack);
    back.show();
    return () => {
      back.offClick(onBack);
      back.hide();
    };
  }, [pathname, navigate]);
}

export default function App() {
  useTelegramBackButton();
  return (
    <>
      <div className="top-bar">
        <span className="app-version">v{import.meta.env.VITE_APP_VERSION ?? "dev"}</span>
        <ProgressSteps />
        <LanguageSwitcher />
      </div>
      <Routes>
        <Route path="/" element={<EntryPage />} />
        <Route path="/scan" element={<ScanPage />} />
        <Route path="/edit/:sessionId" element={<EditItemsPage />} />
        <Route path="/mode/:sessionId" element={<ModePage />} />
        <Route path="/join" element={<JoinPage />} />
        <Route path="/pick/:sessionId" element={<PickPage />} />
        <Route path="/host/:sessionId" element={<HostLivePage />} />
        <Route path="/people/:sessionId" element={<PeoplePage />} />
        <Route path="/assign/:sessionId" element={<AssignPage />} />
        <Route path="/summary/:sessionId" element={<SummaryPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </>
  );
}
