import sys


def main():
    n = int(sys.stdin.read().strip())
    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + b
    sys.stdout.write(str(a) + "\n")


if __name__ == "__main__":
    main()
