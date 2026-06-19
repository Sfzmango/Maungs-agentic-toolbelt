import sys


def main():
    nums = [int(tok) for tok in sys.stdin.read().split()]
    best = nums[0]
    current = nums[0]
    for x in nums[1:]:
        current = max(x, current + x)
        best = max(best, current)
    print(best)


if __name__ == "__main__":
    main()
