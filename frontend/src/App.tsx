import { NavLink, Route, Routes } from "react-router-dom";
import Dashboard from "./pages/Dashboard";
import SessionsPage from "./pages/SessionsPage";
import TranscriptPage from "./pages/TranscriptPage";
import SearchPage from "./pages/SearchPage";
import UploadPage from "./pages/UploadPage";
import LivePage from "./pages/LivePage";
import SettingsPage from "./pages/SettingsPage";
import VocabPage from "./pages/VocabPage";
import NotFound from "./pages/NotFound";

function Sidebar() {
  return (
    <div className="sidebar">
      <h1>SovereignAudio V2</h1>
      <nav>
        <NavLink to="/" end>
          Dashboard
        </NavLink>
        <NavLink to="/upload">Upload / Transcribe</NavLink>
        <NavLink to="/sessions">Sessions</NavLink>
        <NavLink to="/search">Search</NavLink>
        <NavLink to="/settings">Settings</NavLink>
      </nav>
      <div className="sidebar-section">
        <div className="sidebar-label">Advanced</div>
        <NavLink to="/live">Live Mode</NavLink>
        <NavLink to="/vocab">Vocabulary</NavLink>
      </div>
    </div>
  );
}

export default function App() {
  return (
    <div className="layout">
      <Sidebar />
      <div className="content">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/sessions" element={<SessionsPage />} />
          <Route path="/sessions/:sessionId" element={<TranscriptPage />} />
          <Route path="/search" element={<SearchPage />} />
          <Route path="/upload" element={<UploadPage />} />
          <Route path="/live" element={<LivePage />} />
          <Route path="/settings" element={<SettingsPage />} />
          <Route path="/vocab" element={<VocabPage />} />
          <Route path="*" element={<NotFound />} />
        </Routes>
      </div>
    </div>
  );
}
