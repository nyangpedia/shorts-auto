import { VISUAL_STYLES } from "../models";

interface StylePickerProps {
  readonly value: string | null;
  readonly onPick: (styleId: string) => void;
  readonly disabled?: boolean;
}

/** Style cards with a sample picture each (apps/web/public/styles/<id>.jpg, made by tools/dev/style_samples.py). */
export function StylePicker({ value, onPick, disabled }: StylePickerProps) {
  return (
    <div aria-label="화풍" className="style-grid" role="radiogroup">
      {VISUAL_STYLES.map((s) => (
        <button
          aria-checked={value === s.id}
          className="style-card"
          disabled={disabled}
          key={s.id}
          onClick={() => onPick(s.id)}
          role="radio"
          type="button"
        >
          <span className="style-thumb">
            <img alt="" loading="lazy" onError={(e) => e.currentTarget.remove()} src={`/styles/${s.id}.jpg`} />
          </span>
          <b>{s.label}</b>
          <small>{s.blurb}</small>
        </button>
      ))}
    </div>
  );
}
