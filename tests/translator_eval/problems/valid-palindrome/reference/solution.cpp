#include <iostream>
#include <string>
#include <iterator>
using namespace std;

int main() {
    std::string data((std::istreambuf_iterator<char>(std::cin)),
                     std::istreambuf_iterator<char>());
    if (!data.empty() && data.back() == '\n') {
        data.pop_back();
    }
    std::string filtered;
    for (char ch : data) {
        if ((ch >= 'a' && ch <= 'z') || (ch >= '0' && ch <= '9')) {
            filtered += ch;
        } else if (ch >= 'A' && ch <= 'Z') {
            filtered += static_cast<char>(ch - 'A' + 'a');
        }
    }
    std::string reversed(filtered.rbegin(), filtered.rend());
    std::cout << (filtered == reversed ? "true" : "false") << "\n";
    return 0;
}
