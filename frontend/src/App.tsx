import { Routes, Route, Navigate } from "react-router-dom";
import EntryPage from "./pages/EntryPage";
import ScanPage from "./pages/ScanPage";
import EditItemsPage from "./pages/EditItemsPage";
import JoinPage from "./pages/JoinPage";
import PickPage from "./pages/PickPage";
import HostLivePage from "./pages/HostLivePage";
import SummaryPage from "./pages/SummaryPage";
import ProgressSteps from "./components/ProgressSteps";
import LanguageSwitcher from "./components/LanguageSwitcher";
import "./app.css";

export default function App() {
  return (
    <>
      <div className="top-bar">
        <ProgressSteps />
        <LanguageSwitcher />
      </div>
      <Routes>
        <Route path="/" element={<EntryPage />} />
        <Route path="/scan" element={<ScanPage />} />
        <Route path="/edit/:sessionId" element={<EditItemsPage />} />
        <Route path="/join" element={<JoinPage />} />
        <Route path="/pick/:sessionId" element={<PickPage />} />
        <Route path="/host/:sessionId" element={<HostLivePage />} />
        <Route path="/summary/:sessionId" element={<SummaryPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </>
  );
}
