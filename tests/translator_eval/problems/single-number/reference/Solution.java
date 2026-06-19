import java.io.BufferedReader;
import java.io.InputStreamReader;

public class Solution {
    public static void main(String[] args) throws Exception {
        BufferedReader br = new BufferedReader(new InputStreamReader(System.in));
        StringBuilder sb = new StringBuilder();
        String line;
        while ((line = br.readLine()) != null) {
            sb.append(line).append(' ');
        }
        long result = 0;
        for (String tok : sb.toString().trim().split("\\s+")) {
            if (!tok.isEmpty()) {
                result ^= Long.parseLong(tok);
            }
        }
        System.out.println(result);
    }
}
