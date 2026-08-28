import { useState } from "react";

interface Toast {
  id: string;
  message: string;
  type: "success" | "error" | "info";
  icon?: string;
}

let _addToast: (t: Omit<Toast, "id">) => void = () => {};

export function toast(message: string, type: Toast["type"] = "info", icon?: string) {
  _addToast({ message, type, icon });
}

export default function ToastContainer() {
  const [toasts, setToasts] = useState<Toast[]>([]);

  _addToast = ({ message, type, icon }) => {
    const id = Math.random().toString(36).slice(2);
    setToasts((prev) => [...prev, { id, message, type, icon }]);
    setTimeout(() => setToasts((prev) => prev.filter((t) => t.id !== id)), 4000);
  };

  return (
    <div className="toast-container">
      {toasts.map((t) => (
        <div key={t.id} className={`toast ${t.type}`}>
          <span>{t.icon ?? (t.type === "success" ? "✓" : t.type === "error" ? "✗" : "ℹ")}</span>
          {t.message}
        </div>
      ))}
    </div>
  );
}
