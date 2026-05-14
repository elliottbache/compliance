const EMPTY_VALUE = "—";

function padDatePart(value: number): string {
  return String(value).padStart(2, "0");
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) {
    return EMPTY_VALUE;
  }

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return value;
  }

  const year = date.getFullYear();
  const month = padDatePart(date.getMonth() + 1);
  const day = padDatePart(date.getDate());
  const hours = padDatePart(date.getHours());
  const minutes = padDatePart(date.getMinutes());
  const seconds = padDatePart(date.getSeconds());

  return `${year}-${month}-${day} ${hours}:${minutes}:${seconds}`;
}

export function formatArchivedAt(value: string | null | undefined): string {
  return value ? formatDateTime(value) : "Active";
}

export function formatArchiveReason(value: string | null | undefined): string {
  return value?.trim() || EMPTY_VALUE;
}
