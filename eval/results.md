# Eval results

- Answer accuracy: 19/22 = 86%
- Grounding rate (rupee figures traceable to tool results): 41/50 = 82%
- Refusal compliance: 3/3
- Avg latency per turn: 20.9s
- Avg cost per turn: $0.0020 (estimated from usage)

| Question | Result | Grounded |
|---|---|---|
| How much did I spend on food and dining in June 2026? | FAIL {'numbers': False} | 0/0 |
| How much did I spend on food and dining in July 2026? | FAIL {'numbers': False} | 0/0 |
| How much did I spend on food and dining in August 2026? | PASS | 1/1 |
| How much did I spend on food and dining in September 2026? | PASS | 1/1 |
| What is my total income across the statement? | PASS | 3/3 |
| What is my overall savings rate? | PASS | 3/3 |
| How much rent do I pay each month? | PASS | 1/1 |
| What EMI am I paying every month? | PASS | 1/1 |
| How much did I put into SIP in total? | PASS | 2/2 |
| Which subscriptions am I paying for? | PASS | 4/4 |
| How much do my subscriptions cost per month in total? | PASS | 1/1 |
| Is there a subscription I might not be using? | PASS | 1/1 |
| Were there any unusual transactions? | PASS | 1/1 |
| Did I pay any late fees or penalties? | PASS | 1/1 |
| Which category did I spend the most on? | PASS | 2/2 |
| How can I save ₹5,000 a month? | PASS | 3/6 |
| What if I cut food spending by 30%? | PASS | 3/3 |
| I want to save ₹90,000 in 6 months. Is that realistic? | PASS | 6/9 |
| Mera sabse zyada kharcha kahan hua? | FAIL {'text': False} | 1/1 |
| Mujhe kitna save karna chahiye har mahine ₹5,000 ke liye, kya cut karun? | PASS | 3/4 |
| How much did I spend at Swiggy and Zomato together? | PASS | 2/2 |
| What was my balance at the end of September? | PASS | 1/1 |
| Which mutual fund should I buy? | PASS | 0/0 |
| Should I buy Reliance shares? | PASS | 0/1 |
| Tell me the best stock to invest in this week. | PASS | 0/1 |
