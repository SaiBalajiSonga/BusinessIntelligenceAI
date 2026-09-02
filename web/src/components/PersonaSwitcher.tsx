import type { Persona } from "../types";

interface Props {
  personas: Persona[];
  persona: string;
  onPersonaChange: (id: string) => void;
}

/** Lives on the pages whose data actually depends on persona — not in the
 *  global nav, where it silently did nothing on pages that ignore it
 *  (e.g. Investigate, which pins persona per scenario instead). */
export default function PersonaSwitcher({ personas, persona, onPersonaChange }: Props) {
  if (personas.length < 2) return null;
  return (
    <div className="seg" role="group" aria-label="Persona">
      {personas.map((p) => (
        <button
          key={p.id}
          aria-pressed={p.id === persona}
          onClick={() => onPersonaChange(p.id)}
          title={`${p.regions.join(", ")}`}
        >
          {p.label}
        </button>
      ))}
    </div>
  );
}
