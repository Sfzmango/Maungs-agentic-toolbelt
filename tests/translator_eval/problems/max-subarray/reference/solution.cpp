#include <algorithm>
#include <iostream>
#include <vector>
using namespace std;

int main() {
    vector<long long> nums;
    long long x;
    while (std::cin >> x) {
        nums.push_back(x);
    }
    long long best = nums[0];
    long long current = nums[0];
    for (size_t i = 1; i < nums.size(); i++) {
        current = std::max(nums[i], current + nums[i]);
        best = std::max(best, current);
    }
    cout << best << "\n";
    return 0;
}
