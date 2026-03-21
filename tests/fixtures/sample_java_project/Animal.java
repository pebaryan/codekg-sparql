import java.util.List;
import java.util.ArrayList;

public class Animal {
    private String name;
    private int age;

    public Animal(String name, int age) {
        this.name = name;
        this.age = age;
    }

    public String getName() {
        return name;
    }

    public void speak() {
        System.out.println("...");
    }
}
