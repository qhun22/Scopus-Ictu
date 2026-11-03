import { CONFIRMED_IMPORTS_KEY } from "../api/imports";

export const PENDING_SCOPUS_IMPORT_KEY = "scopus-ictu.pending-scopus-import-id";
export const PENDING_LECTURER_PREVIEW_KEY = "scopus-ictu.pending-lecturer-preview";
const PENDING_LECTURER_FILE_STORE = "scopus-ictu.pending-lecturer-file";

function openPendingLecturerFileStore(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(PENDING_LECTURER_FILE_STORE, 1);
    request.onupgradeneeded = () => {
      request.result.createObjectStore("files");
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

export async function savePendingLecturerFile(file: File): Promise<void> {
  const database = await openPendingLecturerFileStore();
  await new Promise<void>((resolve, reject) => {
    const transaction = database.transaction("files", "readwrite");
    transaction.objectStore("files").put(file, "pending");
    transaction.oncomplete = () => resolve();
    transaction.onerror = () => reject(transaction.error);
  });
  database.close();
}

export async function loadPendingLecturerFile(): Promise<File | null> {
  const database = await openPendingLecturerFileStore();
  const file = await new Promise<File | null>((resolve, reject) => {
    const transaction = database.transaction("files", "readonly");
    const request = transaction.objectStore("files").get("pending");
    request.onsuccess = () => resolve((request.result as File | undefined) ?? null);
    request.onerror = () => reject(request.error);
  });
  database.close();
  return file;
}

export async function clearPendingLecturerFile(): Promise<void> {
  const database = await openPendingLecturerFileStore();
  await new Promise<void>((resolve, reject) => {
    const transaction = database.transaction("files", "readwrite");
    transaction.objectStore("files").delete("pending");
    transaction.oncomplete = () => resolve();
    transaction.onerror = () => reject(transaction.error);
  });
  database.close();
}

/**
 * Wipes every client-side cache the Imports page keeps about an in-flight or
 * already-confirmed import (pending Scopus/lecturer preview, confirmed-import
 * ids). These live in the browser (sessionStorage/localStorage/IndexedDB) and
 * are NOT touched by a server-side System Reset, so they must be cleared
 * explicitly whenever the server data they reference may no longer exist.
 */
export function clearAllPendingImportCaches(): void {
  try {
    sessionStorage.removeItem(PENDING_SCOPUS_IMPORT_KEY);
    sessionStorage.removeItem(PENDING_LECTURER_PREVIEW_KEY);
  } catch {
    // sessionStorage can throw in locked-down browser contexts; nothing to clean up then.
  }
  try {
    localStorage.removeItem(CONFIRMED_IMPORTS_KEY);
  } catch {
    // same as above, for localStorage.
  }
  void clearPendingLecturerFile().catch(() => undefined);
}
