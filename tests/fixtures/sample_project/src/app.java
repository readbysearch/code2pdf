package com.example;

/**
 * Sample Java application
 */
public class App {
    public static void main(String[] args) {
        System.out.println("Java Application Started");
        
        Calculator calc = new Calculator();
        int result = calc.add(10, 20);
        System.out.println("10 + 20 = " + result);
    }
}

class Calculator {
    public int add(int a, int b) {
        return a + b;
    }
    
    public int subtract(int a, int b) {
        return a - b;
    }
}