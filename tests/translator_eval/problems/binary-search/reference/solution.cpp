#include <iostream>
#include <string>
#include <sstream>
#include <vector>
using namespace std;

int main() {
    string arrLine, targetLine;
    getline(cin, arrLine);
    getline(cin, targetLine);

    vector<long long> nums;
    {
        istringstream iss(arrLine);
        long long x;
        while (iss >> x) {
            nums.push_back(x);
        }
    }
    long long target = 0;
    {
        istringstream iss(targetLine);
        iss >> target;
    }

    int lo = 0;
    int hi = static_cast<int>(nums.size()) - 1;
    int ans = -1;
    while (lo <= hi) {
        int mid = (lo + hi) / 2;
        if (nums[mid] == target) {
            ans = mid;
            break;
        } else if (nums[mid] < target) {
            lo = mid + 1;
        } else {
            hi = mid - 1;
        }
    }
    cout << ans << "\n";
    return 0;
}
