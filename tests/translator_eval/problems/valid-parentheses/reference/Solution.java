import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.util.ArrayDeque;
import java.util.Deque;

public class Solution {
    public static void main(String[] args) throws Exception {
        BufferedReader br = new BufferedReader(new InputStreamReader(System.in));
        StringBuilder sb = new StringBuilder();
        int c;
        while ((c = br.read()) != -1) {
            sb.append((char) c);
        }
        String data = sb.toString();
        if (data.endsWith("\n")) {
            data = data.substring(0, data.length() - 1);
        }
        Deque<Character> stack = new ArrayDeque<>();
        boolean valid = true;
        for (int i = 0; i < data.length(); i++) {
            char ch = data.charAt(i);
            if (ch == '(' || ch == '[' || ch == '{') {
                stack.push(ch);
            } else if (ch == ')' || ch == ']' || ch == '}') {
                char want = ch == ')' ? '(' : (ch == ']' ? '[' : '{');
                if (stack.isEmpty() || stack.pop() != want) {
                    valid = false;
                    break;
                }
            }
        }
        if (!stack.isEmpty()) {
            valid = false;
        }
        System.out.println(valid ? "true" : "false");
    }
}
