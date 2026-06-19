import sys


def main():
    data = sys.stdin.read()
    if data.endswith("\n"):
        data = data[:-1]
    pairs = {")": "(", "]": "[", "}": "{"}
    stack = []
    valid = True
    for ch in data:
        if ch in "([{":
            stack.append(ch)
        elif ch in ")]}":
            if not stack or stack.pop() != pairs[ch]:
                valid = False
                break
    if stack:
        valid = False
    print("true" if valid else "false")


if __name__ == "__main__":
    main()
