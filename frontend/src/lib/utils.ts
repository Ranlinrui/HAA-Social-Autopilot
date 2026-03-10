import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";
import type { TweetStatus } from "@/types";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatDate(dateStr: string): string {
  if (!dateStr) return "-";
  return new Date(dateStr).toLocaleString("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function formatFileSize(bytes?: number): string {
  if (!bytes) return "-";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function getStatusColor(status: TweetStatus): string {
  const map: Record<TweetStatus, string> = {
    draft: "bg-gray-100 text-gray-700",
    scheduled: "bg-blue-100 text-blue-700",
    publishing: "bg-yellow-100 text-yellow-700",
    published: "bg-green-100 text-green-700",
    failed: "bg-red-100 text-red-700",
  };
  return map[status] ?? "bg-gray-100 text-gray-700";
}

export function getStatusText(status: TweetStatus): string {
  const map: Record<TweetStatus, string> = {
    draft: "草稿",
    scheduled: "已排期",
    publishing: "发布中",
    published: "已发布",
    failed: "失败",
  };
  return map[status] ?? status;
}
