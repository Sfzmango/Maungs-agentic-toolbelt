import sys


def main():
    data = sys.stdin.read()
    if data.endswith("\n"):
        data = data[:-1]
    sys.stdout.write(data[::-1])


if __name__ == "__main__":
    main()
