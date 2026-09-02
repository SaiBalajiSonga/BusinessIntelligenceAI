import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import { startBootstrap } from "./api";
import { FOCAL_WEEK, DEFAULT_PERSONA } from "./constants";
import "./styles.css";

// Fire the app's one bootstrap request before React mounts. Waiting for a
// component effect would put it behind bundle parse and the first render, and
// the whole point is that the network is busy while that happens. Requests for
// anything it covers wait on it rather than duplicating it, so the first page
// is served by this call too.
startBootstrap(FOCAL_WEEK, DEFAULT_PERSONA);

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
