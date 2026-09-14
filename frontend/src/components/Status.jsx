import { formatLabel, statusTone } from "../lib/format";

export function Status({ value }) {
  if (!value) return null;

  return <span className={`status status--${statusTone(value)}`}>{formatLabel(value)}</span>;
}
