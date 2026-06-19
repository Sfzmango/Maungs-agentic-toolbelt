#include <iostream>
#include <sstream>
#include <string>
#include <unordered_map>
#include <utility>
#include <vector>
using namespace std;

int main() {
    string firstLine, secondLine;
    std::getline(std::cin, firstLine);
    std::getline(std::cin, secondLine);
    vector<long long> nums;
    {
        std::istringstream iss(firstLine);
        long long v;
        while (iss >> v) {
            nums.push_back(v);
        }
    }
    long long target = std::stoll(secondLine);
    std::unordered_map<long long, int> seen;
    int a = -1, b = -1;
    for (int i = 0; i < (int)nums.size(); i++) {
        long long complement = target - nums[i];
        auto it = seen.find(complement);
        if (it != seen.end()) {
            a = it->second;
            b = i;
            break;
        }
        seen[nums[i]] = i;
    }
    if (a > b) {
        std::swap(a, b);
    }
    cout << a << " " << b << "\n";
    return 0;
}
