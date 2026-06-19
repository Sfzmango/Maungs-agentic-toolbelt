#include <iostream>
#include <string>
using namespace std;

int main() {
    string data, line;
    while (getline(cin, line)) {
        data += line;
        data += '\n';
    }
    // trim whitespace
    size_t start = data.find_first_not_of(" \t\r\n");
    size_t end = data.find_last_not_of(" \t\r\n");
    if (start == string::npos) {
        return 0;
    }
    string trimmed = data.substr(start, end - start + 1);
    long long n = stoll(trimmed);
    string out;
    for (long long i = 1; i <= n; i++) {
        if (i % 15 == 0) {
            out += "FizzBuzz";
        } else if (i % 3 == 0) {
            out += "Fizz";
        } else if (i % 5 == 0) {
            out += "Buzz";
        } else {
            out += to_string(i);
        }
        out += '\n';
    }
    cout << out;
    return 0;
}
