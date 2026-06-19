import sys


def main():
    nums = [int(tok) for tok in sys.stdin.read().split()]
    result = 0
    for x in nums:
        result ^= x
    print(result)


if __name__ == "__main__":
    main()
