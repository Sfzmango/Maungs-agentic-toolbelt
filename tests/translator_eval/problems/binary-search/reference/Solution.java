import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.util.ArrayList;
import java.util.List;
import java.util.StringTokenizer;

public class Solution {
    public static void main(String[] args) throws Exception {
        BufferedReader br = new BufferedReader(new InputStreamReader(System.in));
        String arrLine = br.readLine();
        String targetLine = br.readLine();
        if (arrLine == null) {
            arrLine = "";
        }
        if (targetLine == null) {
            targetLine = "";
        }

        List<Long> numsList = new ArrayList<>();
        StringTokenizer st = new StringTokenizer(arrLine);
        while (st.hasMoreTokens()) {
            numsList.add(Long.parseLong(st.nextToken()));
        }
        long target = Long.parseLong(targetLine.trim());

        int lo = 0;
        int hi = numsList.size() - 1;
        int ans = -1;
        while (lo <= hi) {
            int mid = (lo + hi) / 2;
            long v = numsList.get(mid);
            if (v == target) {
                ans = mid;
                break;
            } else if (v < target) {
                lo = mid + 1;
            } else {
                hi = mid - 1;
            }
        }
        System.out.println(ans);
    }
}
