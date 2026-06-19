import sys


def main():
    data = sys.stdin.read()
    if data.endswith("\n"):
        data = data[:-1]
    filtered = [c.lower() for c in data if c.isascii() and c.isalnum()]
    is_pal = filtered == filtered[::-1]
    sys.stdout.write("true\n" if is_pal else "false\n")


if __name__ == "__main__":
    main()
