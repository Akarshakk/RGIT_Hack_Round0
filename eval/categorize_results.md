# Categorization on 40 unseen merchants

- Rules only: 0/40 = 0% (everything unknown falls to Other)
- Rules + LLM fallback (openai/gpt-oss-20b, enum-constrained): 30/40 = 75%

Misses (merchant, expected, got):
- keventers: Food & Dining → Entertainment
- spencers: Groceries → Shopping
- ratnadeep: Groceries → Food & Dining
- moreretail: Groceries → Shopping
- countrydelight: Groceries → Food & Dining
- otipy: Groceries → Transport
- blusmart: Transport → Shopping
- torrentpower: Utilities & Bills → Entertainment
- bwssb: Utilities & Bills → Shopping
- tpddl: Utilities & Bills → Transport
