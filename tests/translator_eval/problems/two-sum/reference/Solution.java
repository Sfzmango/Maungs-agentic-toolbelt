import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.util.HashMap;
import java.util.Map;

public class Solution {
    public static void main(String[] args) throws Exception {
        BufferedReader br = new BufferedReader(new InputStreamReader(System.in));
        String first = br.readLine();
        String second = br.readLine();
        String[] toks = first.trim().split("\\s+");
        long[] nums = new long[toks.length];
        for (int i = 0; i < toks.length; i++) {
            nums[i] = Long.parseLong(toks[i]);
        }
        long target = Long.parseLong(second.trim());
        Map<Long, Integer> seen = new HashMap<>();
        int a = -1;
        int b = -1;
        for (int i = 0; i < nums.length; i++) {
            long complement = target - nums[i];
            if (seen.containsKey(complement)) {
                a = seen.get(complement);
                b = i;
                break;
            }
            seen.put(nums[i], i);
        }
        if (a > b) {
            int t = a;
            a = b;
            b = t;
        }
        System.out.println(a + " " + b);
    }
}
