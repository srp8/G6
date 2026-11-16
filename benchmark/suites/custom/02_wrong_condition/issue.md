# Bug: 18-year-olds are classified as minors

Our policy says adults are people aged 18 **or older**, but
`is_adult(18)` returns False. Fix the comparison in `access.py`.
