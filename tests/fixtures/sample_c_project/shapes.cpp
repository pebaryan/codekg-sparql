#include <iostream>
#include <string>

class Shape {
public:
    virtual double area() {
        return 0.0;
    }

    void describe() {
        std::cout << "Shape with area: " << area() << std::endl;
    }
};

class Circle : public Shape {
    double radius;
public:
    Circle(double r) : radius(r) {}

    double area() {
        return 3.14159 * radius * radius;
    }
};

namespace geometry {
    class Rectangle : public Shape {
        double width, height;
    public:
        Rectangle(double w, double h) : width(w), height(h) {}

        double area() {
            return width * height;
        }
    };

    double compute_total(Shape* shapes[], int count) {
        double total = 0;
        for (int i = 0; i < count; i++) {
            total += shapes[i]->area();
        }
        return total;
    }
}
