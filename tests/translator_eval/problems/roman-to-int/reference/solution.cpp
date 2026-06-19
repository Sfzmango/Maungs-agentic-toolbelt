#include <iostream>
#include <string>
#include <unordered_map>
using namespace std;

int main() {
    string s;
    std::getline(std::cin, s);
    // Trim surrounding whitespace.
    size_t start = s.find_first_not_of(" \t\r\n");
    size_t end = s.find_last_not_of(" \t\r\n");
    if (start == string::npos) {
        s = "";
    } else {
        s = s.substr(start, end - start + 1);
    }
    std::unordered_map<char, int> values = {
        {'I', 1}, {'V', 5}, {'X', 10}, {'L', 50},
        {'C', 100}, {'D', 500}, {'M', 1000}};
    int total = 0;
    for (size_t i = 0; i < s.size(); i++) {
        int v = values[s[i]];
        if (i + 1 < s.size() && values[s[i + 1]] > v) {
            total -= v;
        } else {
            total += v;
        }
    }
    cout << total << "\n";
    return 0;
}
