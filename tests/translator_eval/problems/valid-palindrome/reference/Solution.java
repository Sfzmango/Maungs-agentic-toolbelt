import java.io.BufferedReader;
import java.io.InputStreamReader;

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
        StringBuilder filtered = new StringBuilder();
        for (int i = 0; i < data.length(); i++) {
            char ch = data.charAt(i);
            if ((ch >= 'a' && ch <= 'z') || (ch >= '0' && ch <= '9')) {
                filtered.append(ch);
            } else if (ch >= 'A' && ch <= 'Z') {
                filtered.append((char) (ch - 'A' + 'a'));
            }
        }
        String f = filtered.toString();
        String r = filtered.reverse().toString();
        System.out.println(f.equals(r) ? "true" : "false");
    }
}
