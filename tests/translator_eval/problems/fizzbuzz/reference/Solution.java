import java.io.BufferedReader;
import java.io.InputStreamReader;

public class Solution {
    public static void main(String[] args) throws Exception {
        BufferedReader br = new BufferedReader(new InputStreamReader(System.in));
        StringBuilder raw = new StringBuilder();
        String line;
        while ((line = br.readLine()) != null) {
            raw.append(line).append('\n');
        }
        String data = raw.toString().trim();
        if (data.isEmpty()) {
            return;
        }
        int n = Integer.parseInt(data);
        StringBuilder out = new StringBuilder();
        for (int i = 1; i <= n; i++) {
            if (i % 15 == 0) {
                out.append("FizzBuzz");
            } else if (i % 3 == 0) {
                out.append("Fizz");
            } else if (i % 5 == 0) {
                out.append("Buzz");
            } else {
                out.append(i);
            }
            out.append('\n');
        }
        System.out.print(out);
    }
}
