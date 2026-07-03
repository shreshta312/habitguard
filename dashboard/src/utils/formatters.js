export function formatMinutes(minutes) {
  const value = Number(minutes || 0);

  if (value < 1) return "0 min";

  const hours = Math.floor(value / 60);
  const mins = Math.round(value % 60);

  if (hours <= 0) return `${mins} min`;
  if (mins === 0) return `${hours}h`;

  return `${hours}h ${mins}m`;
}

export function formatDateTime(value) {
  if (!value) return "Not available";

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return String(value);
  }

  return date.toLocaleString();
}

export function formatKey(key) {
  if (!key) return "";

  const cleanKey = String(key)
    .replace(/_/g, " ")
    .replace(/-/g, " ")
    .trim();

  const isMostlyUppercase =
    cleanKey === cleanKey.toUpperCase() && /[A-Z]/.test(cleanKey);

  if (isMostlyUppercase) {
    return cleanKey
      .toLowerCase()
      .replace(/\b\w/g, (char) => char.toUpperCase());
  }

  return cleanKey
    .replace(/([a-z])([A-Z])/g, "$1 $2")
    .replace(/\s+/g, " ")
    .trim()
    .replace(/^./, (char) => char.toUpperCase());
}