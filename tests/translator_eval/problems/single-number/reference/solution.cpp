#include <iostream>
using namespace std;

int main() {
    long long result = 0;
    long long x;
    while (std::cin >> x) {
        result ^= x;
    }
    cout << result << "\n";
    return 0;
}
