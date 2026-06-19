import sys


def main():
    lines = sys.stdin.read().splitlines()
    nums = [int(tok) for tok in lines[0].split()]
    target = int(lines[1].strip())
    seen = {}
    a, b = -1, -1
    for i, x in enumerate(nums):
        complement = target - x
        if complement in seen:
            a, b = seen[complement], i
            break
        seen[x] = i
    if a > b:
        a, b = b, a
    print(f"{a} {b}")


if __name__ == "__main__":
    main()
