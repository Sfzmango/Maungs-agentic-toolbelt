#include <iostream>
#include <string>
using namespace std;

int main() {
    string data;
    {
        std::string line;
        while (getline(cin, line)) {
            data += line;
        }
    }
    // trim
    size_t start = data.find_first_not_of(" \t\r\n");
    long long n = 0;
    if (start != string::npos) {
        n = stoll(data.substr(start));
    }
    unsigned long long a = 0ULL;
    unsigned long long b = 1ULL;
    for (long long i = 0; i < n; i++) {
        unsigned long long next = a + b;
        a = b;
        b = next;
    }
    cout << a << "\n";
    return 0;
}
