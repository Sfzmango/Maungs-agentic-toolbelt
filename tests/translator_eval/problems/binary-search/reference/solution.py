import sys


def main():
    lines = sys.stdin.read().split("\n")
    arr_line = lines[0] if len(lines) > 0 else ""
    target_line = lines[1] if len(lines) > 1 else ""
    nums = [int(x) for x in arr_line.split()]
    target = int(target_line.strip())

    lo, hi = 0, len(nums) - 1
    ans = -1
    while lo <= hi:
        mid = (lo + hi) // 2
        if nums[mid] == target:
            ans = mid
            break
        elif nums[mid] < target:
            lo = mid + 1
        else:
            hi = mid - 1
    sys.stdout.write(str(ans) + "\n")


if __name__ == "__main__":
    main()
