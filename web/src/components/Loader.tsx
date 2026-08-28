import { useEffect, useState } from "react";

const QUOTES = [
  "\"In God we trust, all others must bring data.\" — W. Edwards Deming",
  "\"Data is what you need to do analytics. Information is what you need to do business.\" — John Owen",
  "\"If we have data, let’s look at data. If all we have are opinions, let’s go with mine.\" — Jim Barksdale",
  "\"The goal is to turn data into information, and information into insight.\" — Carly Fiorina",
  "\"Torture the data, and it will confess to anything.\" — Ronald Coase",
];

interface Props {
  text?: string;
}

export default function Loader({ text = "Loading..." }: Props) {
  const [quoteIndex, setQuoteIndex] = useState(0);

  useEffect(() => {
    // Rotate quote every 3.5 seconds
    const interval = setInterval(() => {
      setQuoteIndex((prev) => (prev + 1) % QUOTES.length);
    }, 3500);
    return () => clearInterval(interval);
  }, []);

  return (
    <div style={{
      display: "flex",
      flexDirection: "column",
      alignItems: "center",
      justifyContent: "center",
      height: "60vh",
      width: "100%",
      textAlign: "center"
    }}>
      <div className="loader-animation" style={{ marginBottom: 24 }}>
        <div className="cube" />
        <div className="cube" />
        <div className="cube" />
        <div className="cube" />
      </div>
      
      <div style={{ fontSize: 16, fontWeight: 600, color: "var(--ink)", marginBottom: 12, letterSpacing: "-0.01em" }}>
        {text}
      </div>
      
      <div style={{ 
        maxWidth: 400, 
        fontSize: 13, 
        color: "var(--muted)", 
        fontStyle: "italic",
        lineHeight: 1.6,
        opacity: 0.8,
        transition: "opacity 0.5s ease"
      }} key={quoteIndex}>
        {QUOTES[quoteIndex]}
      </div>
    </div>
  );
}
