import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.util.HashMap;
import java.util.Map;

public class Solution {
    public static void main(String[] args) throws Exception {
        BufferedReader br = new BufferedReader(new InputStreamReader(System.in));
        StringBuilder sb = new StringBuilder();
        int c;
        while ((c = br.read()) != -1) {
            sb.append((char) c);
        }
        String s = sb.toString().trim();
        Map<Character, Integer> values = new HashMap<>();
        values.put('I', 1);
        values.put('V', 5);
        values.put('X', 10);
        values.put('L', 50);
        values.put('C', 100);
        values.put('D', 500);
        values.put('M', 1000);
        int total = 0;
        for (int i = 0; i < s.length(); i++) {
            int v = values.get(s.charAt(i));
            if (i + 1 < s.length() && values.get(s.charAt(i + 1)) > v) {
                total -= v;
            } else {
                total += v;
            }
        }
        System.out.println(total);
    }
}
