import "./App.css";
import { Routes, Route } from "react-router-dom";
import LoginPage from "./pages/LoginPage";
import LocalSelectPage from "./pages/LocalSelectPage";

function App() {


  return (
    <Routes>

      <Route path="/login" element={<LoginPage />} />
      <Route path="/local_select" element={<LocalSelectPage />} />

    </Routes>
  );
}


export default App;
