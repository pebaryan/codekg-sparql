interface Validatable {
    validate(): boolean;
}

class BaseModel implements Validatable {
    validate(): boolean {
        return true;
    }
}

class User extends BaseModel {
    constructor(public name: string, public email: string) {
        super();
    }

    greet(): string {
        return `Hello, ${this.name}!`;
    }
}

class AdminUser extends User {
    role: string;

    constructor(name: string, email: string, role: string = "admin") {
        super(name, email);
        this.role = role;
    }

    hasPermission(perm: string): boolean {
        return true;
    }
}

export { User, AdminUser, BaseModel, Validatable };
