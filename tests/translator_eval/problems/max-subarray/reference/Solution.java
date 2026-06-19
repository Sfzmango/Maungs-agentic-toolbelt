import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.util.ArrayList;
import java.util.List;

public class Solution {
    public static void main(String[] args) throws Exception {
        BufferedReader br = new BufferedReader(new InputStreamReader(System.in));
        StringBuilder sb = new StringBuilder();
        String line;
        while ((line = br.readLine()) != null) {
            sb.append(line).append(' ');
        }
        List<Long> nums = new ArrayList<>();
        for (String tok : sb.toString().trim().split("\\s+")) {
            if (!tok.isEmpty()) {
                nums.add(Long.parseLong(tok));
            }
        }
        long best = nums.get(0);
        long current = nums.get(0);
        for (int i = 1; i < nums.size(); i++) {
            long x = nums.get(i);
            current = Math.max(x, current + x);
            best = Math.max(best, current);
        }
        System.out.println(best);
    }
}
