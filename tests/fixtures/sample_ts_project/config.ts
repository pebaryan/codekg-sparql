import { readFileSync } from "fs";

export const DEFAULT_PORT = 8080;
export const CONFIG_PATH = "config.yaml";

export function parseConfig(path: string): Record<string, unknown> {
    const raw = readFileSync(path, "utf-8");
    return JSON.parse(raw);
}

export function validateConfig(config: Record<string, unknown>): boolean {
    const required = ["host", "port", "debug"];
    for (const key of required) {
        if (!(key in config)) {
            return false;
        }
    }
    return true;
}
