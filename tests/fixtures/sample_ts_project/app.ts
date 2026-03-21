import { parseConfig, validateConfig } from "./config";
import { User, AdminUser } from "./models";

export function createApp(configPath: string) {
    const config = parseConfig(configPath);
    if (!validateConfig(config)) {
        throw new Error("Invalid config");
    }
    return { config };
}

export const handleRequest = (user: User, action: string) => {
    user.validate();
    const greeting = user.greet();
    console.log(greeting);
    return processAction(action);
};

function processAction(action: string) {
    return { action, status: "ok" };
}

function main() {
    const app = createApp("config.yaml");
    const admin = new AdminUser("Admin", "admin@example.com", "admin");
    handleRequest(admin, "dashboard");
}
