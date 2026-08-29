import { request } from "./client";

export interface AppVersion {
  app_name: string;
  version: string;
}

export interface VersionCheck {
  current: string;
  latest: string | null;
  has_update: boolean;
  error: string | null;
}

export function getAppVersion(): Promise<AppVersion> {
  return request<AppVersion>("/version");
}

export function checkAppVersion(): Promise<VersionCheck> {
  return request<VersionCheck>("/version/check");
}
