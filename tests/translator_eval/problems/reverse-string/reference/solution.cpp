#include <iostream>
#include <string>
#include <algorithm>
#include <iterator>
using namespace std;

int main() {
    std::string data((std::istreambuf_iterator<char>(std::cin)),
                     std::istreambuf_iterator<char>());
    if (!data.empty() && data.back() == '\n') {
        data.pop_back();
    }
    std::reverse(data.begin(), data.end());
    std::cout << data;
    return 0;
}
