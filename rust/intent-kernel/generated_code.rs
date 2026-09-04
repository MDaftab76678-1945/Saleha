fn main() {
    // Test case 1: Simple palindrome (all lowercase)
    assert!(is_palindrome("racecar"), "Test 1 failed: racecar");

    // Test case 2: Palindrome with mixed case and spaces/punctuation (clas
(classic example)
    // 

    // Test case 3: Simple palindrome with mixed case
    assert!(is_palindrome("RaceCar"), "Test 3 failed: RaceCar");

    // Test case 4: Not a palindrome
    assert!(!is_palindrome("hello world"), "Test 4 failed: hello world");

    // Test case 5: Edge case - empty string
    assert!(is_palindrome(""), "Test 5 failed: Empty string");

    // Test case 6: Edge case - only non-alphanumeric characters
    assert!(is_palindrome("!@#$%^&*()"), "Test 6 failed: Only symbols");

    // Test case 7: Single character palindrome
    assert!(is_palindrome("X"), "Test 7 failed: Single char");

    println!("All palindrome tests passed successfully.");
}