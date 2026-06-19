#include <iostream>
#include <sstream>
#include <string>
using namespace std;

int main() {
    std::ostringstream ss;
    ss << std::cin.rdbuf();
    string data = ss.str();
    if (!data.empty() && data.back() == '\n') {
        data.pop_back();
    }
    string stack;
    bool valid = true;
    for (char ch : data) {
        if (ch == '(' || ch == '[' || ch == '{') {
            stack.push_back(ch);
        } else if (ch == ')' || ch == ']' || ch == '}') {
            char want = ch == ')' ? '(' : (ch == ']' ? '[' : '{');
            if (stack.empty() || stack.back() != want) {
                valid = false;
                break;
            }
            stack.pop_back();
        }
    }
    if (!stack.empty()) {
        valid = false;
    }
    cout << (valid ? "true" : "false") << "\n";
    return 0;
}
