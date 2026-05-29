import { Routes, Route, Navigate } from "react-router-dom";
import ScanPage from "./pages/ScanPage";
import EditItemsPage from "./pages/EditItemsPage";
import PeoplePage from "./pages/PeoplePage";
import AssignPage from "./pages/AssignPage";
import SummaryPage from "./pages/SummaryPage";
import ProgressSteps from "./components/ProgressSteps";
import "./app.css";

export default function App() {
  return (
    <>
      <ProgressSteps />
      <Routes>
        <Route path="/" element={<ScanPage />} />
        <Route path="/edit/:sessionId" element={<EditItemsPage />} />
        <Route path="/people/:sessionId" element={<PeoplePage />} />
        <Route path="/assign/:sessionId" element={<AssignPage />} />
        <Route path="/summary/:sessionId" element={<SummaryPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </>
  );
}
