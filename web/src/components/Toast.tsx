import { useState } from "react";
import { CheckCircle2, XCircle, Info } from "lucide-react";

interface Toast {
  id: string;
  message: string;
  type: "success" | "error" | "info";
}

const TYPE_ICON = { success: CheckCircle2, error: XCircle, info: Info };

let _addToast: (t: Omit<Toast, "id">) => void = () => {};

export function toast(message: string, type: Toast["type"] = "info") {
  _addToast({ message, type });
}

export default function ToastContainer() {
  const [toasts, setToasts] = useState<Toast[]>([]);

  _addToast = ({ message, type }) => {
    const id = Math.random().toString(36).slice(2);
    setToasts((prev) => [...prev, { id, message, type }]);
    setTimeout(() => setToasts((prev) => prev.filter((t) => t.id !== id)), 4000);
  };

  return (
    <div className="toast-container">
      {toasts.map((t) => {
        const Icon = TYPE_ICON[t.type];
        return (
          <div key={t.id} className={`toast ${t.type}`}>
            <span className="toast-icon"><Icon size={17} /></span>
            {t.message}
          </div>
        );
      })}
    </div>
  );
}
